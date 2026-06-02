from fastapi import APIRouter, Request, HTTPException
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
):
    redis: Redis = request.app.state.sync_redis
    now = time.time()
    start_time = now - 600

    pipe = redis.pipeline()

    for i in range(entries):
        ts = start_time + (i / max(entries, 1)) * 600
        pipe.zadd('entries', {f'entry:{int(now)}:{i}': ts})

    for i in range(exits):
        ts = start_time + (i / max(exits, 1)) * 600
        pipe.zadd('exits', {f'exit:{int(now)}:{i}': ts})
        dwell_vari = dwell_seconds * (0.5 + 0.5 * (i / max(exits, 1)))
        pipe.hset('dwell_times', f'exit:{int(now)}:{i}', dwell_vari)

    pipe.incrby('cv:stats:anomalies', anomalies)
    current_occupancy = max(0, entries - exits)
    existing_peak = int(redis.get('peak_occupancy') or 0)
    pipe.set('peak_occupancy', max(existing_peak, current_occupancy))
    pipe.set('staff_count', 5)
    pipe.set('camera_fps', 25.0)
    pipe.set('cv:heatmap:10x10', json.dumps([[1]*10 for _ in range(10)]))
    pipe.sadd('cv:tracks', *[f'track_{i}' for i in range(max(entries, exits) + 10)])
    pipe.incrby('cv:pipeline:frames_processed', 1000)
    pipe.set('cv:pipeline:last_frame_id', int(now))
    pipe.set('cv:pipeline:unique_tracks_seen', max(entries, exits) + 50)
    pipe.incrby('cv:pipeline:events_published', entries + exits + anomalies)
    pipe.set('cv:pipeline:worker_last_heartbeat', datetime.datetime.now(datetime.timezone.utc).isoformat())
    pipe.set('cv:metrics:last_updated', datetime.datetime.now(datetime.timezone.utc).isoformat())
    pipe.execute()

    return {
        "status": "simulation_complete",
        "entries_added": entries,
        "exits_added": exits,
        "anomalies_added": anomalies,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


@router.get("/pipeline/status", tags=["Debug"])
async def pipeline_status(request: Request):
    redis: Redis = request.app.state.sync_redis
    return {
        "frames_processed": int(redis.get('cv:pipeline:frames_processed') or 0),
        "last_frame_id": int(redis.get('cv:pipeline:last_frame_id') or 0),
        "unique_tracks_seen": int(redis.get('cv:pipeline:unique_tracks_seen') or 0),
        "events_published": int(redis.get('cv:pipeline:events_published') or 0),
        "worker_last_heartbeat": redis.get('cv:pipeline:worker_last_heartbeat')
    }


@router.get("/health/integrity", tags=["Debug"])
async def health_integrity(request: Request):
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
        "metrics_last_updated": metrics_last_updated,
        "worker_last_heartbeat": worker_last_heartbeat,
        "redis_keys_count": redis_keys_count,
        "kafka_messages_produced": kafka_messages_produced,
        "status": status
    }