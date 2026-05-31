from fastapi import APIRouter, HTTPException
from redis import Redis
import datetime
import time
import json
from typing import Optional

router = APIRouter()

def get_redis():
    """
    Dependency to get Redis client.
    In a real application, this would be configured via environment variables or app state.
    """
    return Redis(host='localhost', port=6379, db=0, decode_responses=True)


@router.post("/api/v1/simulate", tags=["Debug"])
async def simulate(
    entries: int,
    exits: int,
    anomalies: int,
    dwell_seconds: int,
    redis: Redis = Depends(get_redis)
):
    """
    Simulate store traffic by writing realistic event data to Redis.
    Used for testing and demonstration.
    """
    now = time.time()
    
    # Simulate entries and exits as sorted sets with timestamps
    # We'll spread the events over the last 10 minutes to simulate recent activity
    start_time = now - 600  # 10 minutes ago
    
    pipe = redis.pipeline()
    
    # Clear previous simulation data for a clean test? 
    # Instead, we'll just add new events. The demo will show changes.
    
    # Add entry events
    for i in range(entries):
        # Spread timestamps over the last 10 minutes
        ts = start_time + (i / max(entries, 1)) * 600
        pipe.zadd('entries', {f'entry:{int(now)}:{i}': ts})
    
    # Add exit events
    for i in range(exits):
        ts = start_time + (i / max(exits, 1)) * 600
        pipe.zadd('exits', {f'exit:{int(now)}:{i}': ts})
        # Also store dwell time for each exit (assuming dwell_seconds is average)
        # We'll vary it a bit
        dwell_vari = dwell_seconds * (0.5 + 0.5 * (i / max(exits, 1)))  # from 50% to 150% of average
        pipe.hset('dwell_times', f'exit:{int(now)}:{i}', dwell_vari)
    
    # Simulate anomalies by incrementing the anomaly count
    pipe.incrby('cv:stats:anomalies', anomalies)
    
    # Update other metrics to make the simulation realistic
    # Update peak occupancy based on entries-exits
    current_occupancy = max(0, entries - exits)
    pipe.set('peak_occupancy', max(int(redis.get('peak_occupancy') or 0), current_occupancy))
    pipe.set('staff_count', 5)  # assume 5 staff
    pipe.set('camera_fps', 25.0)
    
    # Update heatmap with some dummy data
    pipe.set('cv:heatmap:10x10', json.dumps([[1]*10 for _ in range(10)]))
    
    # Update some track IDs to show unique tracks
    pipe.sadd('cv:tracks', *[f'track_{i}' for i in range(max(entries, exits) + 10)])
    
    # Update last frame ID and frames processed (for pipeline status)
    pipe.incrby('cv:pipeline:frames_processed', 1000)  # simulate 1000 frames
    pipe.set('cv:pipeline:last_frame_id', int(now))
    pipe.set('cv:pipeline:unique_tracks_seen', max(entries, exits) + 50)
    pipe.incrby('cv:pipeline:events_published', entries + exits + anomalies)
    pipe.set('cv:pipeline:worker_last_heartbeat', datetime.datetime.now(datetime.timezone.utc).isoformat())
    
    # Update metrics last updated time for integrity check
    pipe.set('cv:metrics:last_updated', datetime.datetime.now(datetime.timezone.utc).isoformat())
    
    pipe.execute()
    
    return {
        "status": "simulation_complete",
        "entries_added": entries,
        "exits_added": exits,
        "anomalies_added": anomalies,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }


@router.get("/api/v1/pipeline/status", tags=["Debug"])
async def pipeline_status(redis: Redis = Depends(get_redis)):
    """
    Returns current pipeline status from Redis counters.
    """
    frames_processed = int(redis.get('cv:pipeline:frames_processed') or 0)
    last_frame_id = int(redis.get('cv:pipeline:last_frame_id') or 0)
    unique_tracks_seen = int(redis.get('cv:pipeline:unique_tracks_seen') or 0)
    events_published = int(redis.get('cv:pipeline:events_published') or 0)
    worker_last_heartbeat = redis.get('cv:pipeline:worker_last_heartbeat')
    
    return {
        "frames_processed": frames_processed,
        "last_frame_id": last_frame_id,
        "unique_tracks_seen": unique_tracks_seen,
        "events_published": events_published,
        "worker_last_heartbeat": worker_last_heartbeat
    }


@router.get("/api/v1/health/integrity", tags=["Debug"])
async def health_integrity(redis: Redis = Depends(get_redis)):
    """
    Returns integrity health check.
    """
    metrics_last_updated = redis.get('cv:metrics:last_updated')
    worker_last_heartbeat = redis.get('cv:pipeline:worker_last_heartbeat')
    redis_keys_count = int(redis.dbsize())
    kafka_messages_produced = int(redis.get('cv:pipeline:events_published') or 0)
    
    status = "no_data"
    if metrics_last_updated and worker_last_heartbeat:
        # Check if metrics are stale (older than 5 minutes)
        try:
            last_updated = datetime.datetime.fromisoformat(metrics_last_updated.replace('Z', '+00:00'))
            now = datetime.datetime.now(datetime.timezone.utc)
            if (now - last_updated).total_seconds() < 300:  # 5 minutes
                status = "healthy"
            else:
                status = "stale"
        except Exception:
            status = "stale"
    elif not metrics_last_updated and not worker_last_heartbeat:
        status = "no_data"
    
    return {
        "metrics_last_updated": metrics_last_updated,
        "worker_last_heartbeat": worker_last_heartbeat,
        "redis_keys_count": redis_keys_count,
        "kafka_messages_produced": kafka_messages_produced,
        "status": status
    }