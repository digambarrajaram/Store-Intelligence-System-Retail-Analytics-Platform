from fastapi import APIRouter, Depends, Query
from redis import Redis
import datetime
import time
from typing import Optional

router = APIRouter()

def get_redis():
    """
    Dependency to get Redis client.
    In a real application, this would be configured via environment variables or app state.
    """
    return Redis(host='localhost', port=6379, db=0, decode_responses=True)

@router.get("/metrics")
async def get_metrics(
    window_minutes: int = Query(60, ge=1, le=1440),  # Max 24 hours
    redis: Redis = Depends(get_redis)
):
    """
    Returns store KPIs for a time window.
    """
    now = time.time()
    start = now - (window_minutes * 60)
    
    # Get counts from sorted sets (time-based)
    total_entries = redis.zcount('entries', start, now)
    total_exits = redis.zcount('exits', start, now)
    
    # Calculate current occupancy (entries - exits in window)
    # Note: This assumes we start counting from empty at window start
    # For more accurate current occupancy, we would need real-time tracking
    current_occupancy = max(0, total_entries - total_exits)
    
    # Get dwell times for exits in window
    exited_track_ids = redis.zrangebyscore('exits', start, now)
    total_dwell_time_seconds = 0
    valid_exits = 0
    
    for track_id in exited_track_ids:
        # Get dwell time from hash (stored in seconds)
        dwell_time = redis.hget('dwell_times', track_id)
        if dwell_time is not None:
            try:
                total_dwell_time_seconds += float(dwell_time)
                valid_exits += 1
            except ValueError:
                pass
    
    avg_dwell_minutes = (total_dwell_time_seconds / 60) / valid_exits if valid_exits > 0 else 0
    
    # Get other metrics from keys (updated by data pipeline)
    peak_occupancy = int(redis.get('peak_occupancy') or 0)
    staff_count = int(redis.get('staff_count') or 0)
    anomaly_count = int(redis.get('anomaly_count') or 0)
    camera_fps = float(redis.get('camera_fps') or 0)
    
    # Calculate period timestamps
    period_start = datetime.datetime.fromtimestamp(start, tz=datetime.timezone.utc)
    period_end = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc)
    
    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_entries": total_entries,
        "total_exits": total_exits,
        "current_occupancy": current_occupancy,
        "peak_occupancy": peak_occupancy,
        "avg_dwell_minutes": round(avg_dwell_minutes, 2),
        "staff_count": staff_count,
        "anomaly_count": anomaly_count,
        "camera_fps": round(camera_fps, 2)
    }

@router.get("/funnel")
async def get_funnel(
    window_minutes: int = Query(60, ge=1, le=1440),  # Max 24 hours
    redis: Redis = Depends(get_redis)
):
    """
    Returns session-based conversion funnel for a time window.
    Uses sets to avoid double counting per session (track_id).
    """
    now = time.time()
    start = now - (window_minutes * 60)
    
    # Get track_ids that entered store in window
    entered_store = redis.smembers('funnel:entered_store')
    # Filter by timestamp? We assume the set is maintained for the window
    # For simplicity, we'll use the set as-is (data pipeline should expire old entries)
    entered_store_count = len(entered_store)
    
    # Get track_ids that browsed > 2 minutes
    browsed_gt_2min = redis.smembers('funnel:browsed_gt_2min')
    browsed_gt_2min_count = len(browsed_gt_2min)
    
    # Get track_ids that reached checkout zone
    reached_checkout_zone = redis.smembers('funnel:reached_checkout_zone')
    reached_checkout_zone_count = len(reached_checkout_zone)
    
    # Get track_ids that converted (purchased)
    converted = redis.smembers('funnel:converted')
    converted_count = len(converted)
    
    # Calculate conversion rate
    conversion_rate_pct = (converted_count / entered_store_count * 100) if entered_store_count > 0 else 0
    
    return {
        "entered_store": entered_store_count,
        "browsed_gt_2min": browsed_gt_2min_count,
        "reached_checkout_zone": reached_checkout_zone_count,
        "converted": converted_count,
        "conversion_rate_pct": round(conversion_rate_pct, 2)
    }
}