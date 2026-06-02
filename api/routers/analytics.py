from fastapi import APIRouter, Depends, Query
from redis import Redis
import datetime
import time
import os

router = APIRouter()


def get_redis():
    return Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=0,
        decode_responses=True
    )


@router.get("/metrics")
async def get_metrics(
    window_minutes: int = Query(60, ge=1, le=1440),
    redis: Redis = Depends(get_redis)
):

    now = time.time()
    start = now - (window_minutes * 60)

    total_entries = redis.zcount("entries", start, now)
    total_exits = redis.zcount("exits", start, now)

    current_occupancy = max(
        0,
        total_entries - total_exits
    )

    exited_track_ids = redis.zrangebyscore(
        "exits",
        start,
        now
    )

    total_dwell_time_seconds = 0
    valid_exits = 0

    for track_id in exited_track_ids:

        dwell_time = redis.hget(
            "dwell_times",
            track_id
        )

        if dwell_time is not None:
            try:
                total_dwell_time_seconds += float(
                    dwell_time
                )
                valid_exits += 1
            except ValueError:
                pass

    avg_dwell_minutes = (
        (total_dwell_time_seconds / 60)
        / valid_exits
        if valid_exits > 0
        else 0
    )

    peak_occupancy = int(
        redis.get("peak_occupancy") or 0
    )

    staff_count = int(
        redis.get("staff_count") or 0
    )

    anomaly_count = int(
        redis.get("anomaly_count") or 0
    )

    camera_fps = float(
        redis.get("camera_fps") or 0
    )

    period_start = datetime.datetime.fromtimestamp(
        start,
        tz=datetime.timezone.utc
    )

    period_end = datetime.datetime.fromtimestamp(
        now,
        tz=datetime.timezone.utc
    )

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_entries": total_entries,
        "total_exits": total_exits,
        "current_occupancy": current_occupancy,
        "peak_occupancy": peak_occupancy,
        "avg_dwell_minutes": round(
            avg_dwell_minutes,
            2
        ),
        "staff_count": staff_count,
        "anomaly_count": anomaly_count,
        "camera_fps": round(
            camera_fps,
            2
        )
    }


@router.get("/funnel")
async def get_funnel(
    redis: Redis = Depends(get_redis)
):

    entered_store = redis.smembers(
        "funnel:entered_store"
    )

    browsed_gt_2min = redis.smembers(
        "funnel:browsed_gt_2min"
    )

    reached_checkout_zone = redis.smembers(
        "funnel:reached_checkout_zone"
    )

    converted = redis.smembers(
        "funnel:converted"
    )

    entered_store_count = len(
        entered_store
    )

    browsed_gt_2min_count = len(
        browsed_gt_2min
    )

    reached_checkout_zone_count = len(
        reached_checkout_zone
    )

    converted_count = len(
        converted
    )

    conversion_rate_pct = (
        converted_count
        / entered_store_count
        * 100
        if entered_store_count > 0
        else 0
    )

    return [
        {"step": "Entered Store", "value": entered_store_count},
        {"step": "Browsed > 2 min", "value": browsed_gt_2min_count},
        {"step": "Reached Checkout", "value": reached_checkout_zone_count},
        {"step": "Converted", "value": converted_count}
    ]


@router.get("/occupancy/history")
async def get_occupancy_history(
    window_minutes: int = Query(60, ge=5, le=1440),
    interval_minutes: int = Query(5, ge=1, le=60),
    redis: Redis = Depends(get_redis)
):
    now = time.time()
    start = now - (window_minutes * 60)
    interval_seconds = interval_minutes * 60
    sample_count = min(int(window_minutes // interval_minutes) + 1, 60)

    history = []
    for index in range(sample_count):
        point_time = min(start + (index * interval_seconds), now)
        count = max(
            0,
            redis.zcount("entries", 0, point_time) - redis.zcount("exits", 0, point_time)
        )
        history.append({
            "timestamp": datetime.datetime.fromtimestamp(point_time, tz=datetime.timezone.utc).isoformat(),
            "count": count
        })

    peak_count = max((item["count"] for item in history), default=0)

    return {
        "window_minutes": window_minutes,
        "interval_minutes": interval_minutes,
        "peak_count": peak_count,
        "history": history
    }


@router.get("/kpis")
async def get_kpis(
    window_minutes: int = Query(60, ge=1, le=1440),
    redis: Redis = Depends(get_redis)
):
    now = time.time()
    start = now - (window_minutes * 60)
    
    # Get entries and exits for the time window
    total_entries = redis.zcount("entries", start, now)
    total_exits = redis.zcount("exits", start, now)
    current_occupancy = max(0, total_entries - total_exits)
    
    # Calculate occupancy trend (compare first half vs second half of window)
    mid_point = start + (window_minutes * 60) / 2
    entries_first_half = redis.zcount("entries", start, mid_point)
    exits_first_half = redis.zcount("exits", start, mid_point)
    occupancy_first_half = max(0, entries_first_half - exits_first_half)
    
    entries_second_half = redis.zcount("entries", mid_point, now)
    exits_second_half = redis.zcount("exits", mid_point, now)
    occupancy_second_half = max(0, entries_second_half - exits_second_half)
    
    if occupancy_second_half > occupancy_first_half:
        occupancy_trend = 'up'
    elif occupancy_second_half < occupancy_first_half:
        occupancy_trend = 'down'
    else:
        occupancy_trend = 'stable'
    
    # Get sparkline data (last 30 minutes, or available window if less)
    sparkline_window = min(30, window_minutes)
    sparkline_start = now - (sparkline_window * 60)
    
    # Get entry counts per minute for the sparkline
    entriesTodaySparkline = []
    for i in range(sparkline_window):
        point_start = sparkline_start + (i * 60)
        point_end = point_start + 60
        count = redis.zcount("entries", point_start, point_end)
        entriesTodaySparkline.append(count)
    
    # Get conversion rate from funnel data
    entered_store = redis.smembers("funnel:entered_store")
    converted = redis.smembers("funnel:converted")
    entered_store_count = len(entered_store)
    converted_count = len(converted)
    conversion_rate = (converted_count / entered_store_count * 100) if entered_store_count > 0 else 0
    
    # Get active anomalies count (assuming we store this in Redis)
    active_anomalies = int(redis.get("active_anomalies") or 0)
    
    return {
        "currentOccupancy": current_occupancy,
        "occupancyTrend": occupancy_trend,
        "totalEntriesToday": total_entries,  # Using window as proxy for today
        "entriesTodaySparkline": entriesTodaySparkline,
        "conversionRate": round(conversion_rate, 2),
        "activeAnomalies": active_anomalies
    }