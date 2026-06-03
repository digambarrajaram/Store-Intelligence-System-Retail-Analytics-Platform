from fastapi import APIRouter, Request, HTTPException, Query
from redis import Redis
import datetime
import time
import json
import os
from typing import Optional

router = APIRouter()

@router.post("/simulate", tags=["Debug"])
async def simulate(
    request: Request,
    entries: int,
    exits: int,
    anomalies: int,
    dwell_seconds: int,
    store_id: str = Query("store_1"),
    camera_id: str = Query("camera_0"),
):
    redis: Redis = request.app.state.sync_redis
    now = time.time()
    start_time = now - 600

    pipe = redis.pipeline()

    for i in range(entries):
        ts = start_time + (i / max(entries, 1)) * 600
        pipe.zadd(f'store:{store_id}:camera:{camera_id}:entries', {f'entry:{int(now)}:{i}': ts})
        # Also add to store-wide
        pipe.zadd(f'store:{store_id}:entries', {f'{camera_id}:entry:{int(now)}:{i}': ts})

    for i in range(exits):
        ts = start_time + (i / max(exits, 1)) * 600
        pipe.zadd(f'store:{store_id}:camera:{camera_id}:exits', {f'exit:{int(now)}:{i}': ts})
        pipe.zadd(f'store:{store_id}:exits', {f'{camera_id}:exit:{int(now)}:{i}': ts})
        dwell_vari = dwell_seconds * (0.5 + 0.5 * (i / max(exits, 1)))
        pipe.hset(f'store:{store_id}:camera:{camera_id}:dwell_times', f'exit:{int(now)}:{i}', dwell_vari)

    pipe.incrby(f'store:{store_id}:camera:{camera_id}:anomaly_count', anomalies)
    current_occupancy = max(0, entries - exits)
    existing_peak = int(redis.get(f'store:{store_id}:camera:{camera_id}:peak_occupancy') or 0)
    pipe.set(f'store:{store_id}:camera:{camera_id}:peak_occupancy', max(existing_peak, current_occupancy))
    pipe.set(f'store:{store_id}:camera:{camera_id}:fps', 25.0)
    pipe.set(f'store:{store_id}:camera:{camera_id}:current_occupancy', current_occupancy)
    pipe.set('cv:heatmap:10x10', json.dumps([[1]*10 for _ in range(10)]))
    pipe.sadd(f'store:{store_id}:camera:{camera_id}:active_tracks', *[f'track_{i}' for i in range(max(entries, exits) + 10)])
    pipe.incrby('cv:pipeline:frames_processed', 1000)
    pipe.set('cv:pipeline:last_frame_id', int(now))
    pipe.set('cv:pipeline:unique_tracks_seen', max(entries, exits) + 50)
    pipe.incrby('cv:pipeline:events_published', entries + exits + anomalies)
    pipe.set('cv:pipeline:worker_last_heartbeat', datetime.datetime.now(datetime.timezone.utc).isoformat())
    pipe.set('cv:metrics:last_updated', datetime.datetime.now(datetime.timezone.utc).isoformat())
    pipe.execute()

    return {
        "status": "simulation_complete",
        "store_id": store_id,
        "camera_id": camera_id,
        "entries_added": entries,
        "exits_added": exits,
        "anomalies_added": anomalies,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


@router.get("/pipeline/status", tags=["Debug"])
async def pipeline_status(
    request: Request,
    store_id: str = Query("store_1"),
    camera_id: str = Query("camera_0"),
):
    redis: Redis = request.app.state.sync_redis
    return {
        "store_id": store_id,
        "camera_id": camera_id,
        "frames_processed": int(redis.get('cv:pipeline:frames_processed') or 0),
        "last_frame_id": int(redis.get('cv:pipeline:last_frame_id') or 0),
        "unique_tracks_seen": int(redis.get('cv:pipeline:unique_tracks_seen') or 0),
        "events_published": int(redis.get('cv:pipeline:events_published') or 0),
        "worker_last_heartbeat": redis.get('cv:pipeline:worker_last_heartbeat')
    }


@router.get("/health/integrity", tags=["Debug"])
async def health_integrity(
    request: Request,
    store_id: str = Query("store_1"),
    camera_id: str = Query("camera_0"),
):
    redis: Redis = request.app.state.sync_redis
    metrics_last_updated = redis.get('cv:metrics:last_updated')
    worker_last_heartbeat = redis.get('cv:pipeline:worker_last_heartbeat')
    redis_keys_count = int(redis.dbsize())
    kafka_messages_produced = int(redis.get('cv:pipeline:events_published') or 0)

    status = "no_data"
    if metrics_last_updated:
        try:
            last_updated = datetime.datetime.fromisoformat(metrics_last_updated.replace('Z', '+00:00'))
            now = datetime.datetime.now(datetime.timezone.utc)
            status = "healthy" if (now - last_updated).total_seconds() < 300 else "stale"
        except Exception:
            status = "stale"

    return {
        "store_id": store_id,
        "camera_id": camera_id,
        "metrics_last_updated": metrics_last_updated,
        "worker_last_heartbeat": worker_last_heartbeat,
        "redis_keys_count": redis_keys_count,
        "kafka_messages_produced": kafka_messages_produced,
        "status": status
    }
