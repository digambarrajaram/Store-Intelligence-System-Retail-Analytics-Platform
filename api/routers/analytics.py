from fastapi import APIRouter, Query, Request
from redis import Redis
import datetime
import time

router = APIRouter()


@router.get("/store-metrics")
async def get_metrics(
    request: Request,
    window_minutes: int = Query(60, ge=1, le=1440),
    camera_id: str = Query(None),
):
    redis = request.app.state.redis
    now = time.time()
    start = now - (window_minutes * 60)

    # Helper function to get metrics for a specific camera or store-wide
    async def get_camera_metrics(cam_id: str):
        if cam_id:
            entries_key = f"camera:{cam_id}:entries"
            exits_key = f"camera:{cam_id}:exits"
            dwell_key = f"camera:{cam_id}:dwell_times"
            peak_key = f"camera:{cam_id}:peak_occupancy"
            active_tracks_key = f"camera:{cam_id}:active_tracks"
            anomaly_key = f"camera:{cam_id}:anomaly_count"
            fps_key = f"camera:{cam_id}:fps"
        else:
            entries_key = "store:entries"
            exits_key = "store:exits"
            dwell_key = "store:dwell_times"
            peak_key = "store:peak_occupancy"
            active_tracks_key = "store:active_tracks"
            anomaly_key = "store:anomaly_count"
            fps_key = "camera_fps"

        total_entries = await redis.zcount(entries_key, start, now)
        total_exits = await redis.zcount(exits_key, start, now)

        current_occupancy = max(0, total_entries - total_exits)

        exited_track_ids = await redis.zrangebyscore(exits_key, start, now)

        total_dwell_time_seconds = 0
        valid_exits = 0

        for track_id in exited_track_ids:
            dwell_time = await redis.hget(dwell_key, track_id)
            if dwell_time is not None:
                try:
                    total_dwell_time_seconds += float(dwell_time)
                    valid_exits += 1
                except ValueError:
                    pass

        avg_dwell_minutes = (
            (total_dwell_time_seconds / 60) / valid_exits
            if valid_exits > 0
            else 0
        )

        peak_occupancy = int(await redis.get(peak_key) or 0)
        anomaly_count = int(await redis.get(anomaly_key) or 0)
        camera_fps = float(await redis.get(fps_key) or 0)

        return {
            "total_entries": total_entries,
            "total_exits": total_exits,
            "current_occupancy": current_occupancy,
            "peak_occupancy": peak_occupancy,
            "avg_dwell_minutes": round(avg_dwell_minutes, 2),
            "anomaly_count": anomaly_count,
            "camera_fps": round(camera_fps, 2),
        }

    period_start = datetime.datetime.fromtimestamp(
        start, tz=datetime.timezone.utc
    )
    period_end = datetime.datetime.fromtimestamp(
        now, tz=datetime.timezone.utc
    )

    if camera_id == "all":
        # Return per-camera breakdown
        metrics = {}
        for cam_num in range(1, 6):
            cam_id = f"camera_{cam_num}"
            metrics[cam_id] = await get_camera_metrics(cam_id)
        # Add store-wide
        metrics["store"] = await get_camera_metrics(None)
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "cameras": metrics,
        }
    elif camera_id:
        # Return specific camera metrics
        cam_metrics = await get_camera_metrics(camera_id)
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "camera_id": camera_id,
            **cam_metrics,
        }
    else:
        # Return store-wide metrics
        cam_metrics = await get_camera_metrics(None)
        return {
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            **cam_metrics,
        }


@router.get("/funnel")
async def get_funnel(request: Request, camera_id: str = Query(None)):
    redis = request.app.state.redis

    # Helper function to get funnel for a specific camera or store-wide
    async def get_camera_funnel(cam_id: str):
        if cam_id:
            prefix = f"funnel:camera:{cam_id}:"
        else:
            prefix = "funnel:store:"

        entered_store = await redis.smembers(f"{prefix}entered_store") or set()
        browsed_gt_2min = await redis.smembers(f"{prefix}browsed_gt_2min") or set()
        reached_checkout_zone = await redis.smembers(f"{prefix}reached_checkout_zone") or set()
        converted = await redis.smembers(f"{prefix}converted") or set()

        return [
            {"step": "Entered Store", "value": len(entered_store)},
            {"step": "Browsed > 2 min", "value": len(browsed_gt_2min)},
            {"step": "Reached Checkout", "value": len(reached_checkout_zone)},
            {"step": "Converted", "value": len(converted)},
        ]

    if camera_id == "all":
        # Return per-camera breakdown
        funnel_data = {}
        for cam_num in range(1, 6):
            cam_id = f"camera_{cam_num}"
            funnel_data[cam_id] = await get_camera_funnel(cam_id)
        funnel_data["store"] = await get_camera_funnel(None)
        return funnel_data
    elif camera_id:
        # Return specific camera funnel
        return await get_camera_funnel(camera_id)
    else:
        # Return store-wide funnel
        return await get_camera_funnel(None)


@router.get("/occupancy/history")
async def get_occupancy_history(
    request: Request,
    window_minutes: int = Query(60, ge=5, le=1440),
    interval_minutes: int = Query(5, ge=1, le=60),
    camera_id: str = Query(None),
):
    redis = request.app.state.redis
    now = time.time()
    start = now - (window_minutes * 60)
    interval_seconds = interval_minutes * 60
    sample_count = min(int(window_minutes // interval_minutes) + 1, 60)

    # Determine which keys to use
    if camera_id:
        entries_key = f"camera:{camera_id}:entries"
        exits_key = f"camera:{camera_id}:exits"
    else:
        entries_key = "store:entries"
        exits_key = "store:exits"

    history = []
    for index in range(sample_count):
        point_time = min(start + (index * interval_seconds), now)
        entries = await redis.zcount(entries_key, 0, point_time)
        exits = await redis.zcount(exits_key, 0, point_time)
        count = max(0, entries - exits)
        history.append({
            "timestamp": datetime.datetime.fromtimestamp(
                point_time, tz=datetime.timezone.utc
            ).isoformat(),
            "count": count,
        })

    return history


@router.get("/kpis")
async def get_kpis(
    request: Request,
    window_minutes: int = Query(60, ge=1, le=1440),
):
    redis: Redis = request.app.state.redis
    now = time.time()
    start = now - (window_minutes * 60)
    
    # Get entries and exits for the time window
    total_entries = await redis.zcount("entries", start, now)
    total_exits = await redis.zcount("exits", start, now)
    current_occupancy = max(0, total_entries - total_exits)
    
    # Calculate occupancy trend (compare first half vs second half of window)
    mid_point = start + (window_minutes * 60) / 2
    entries_first_half = await redis.zcount("entries", start, mid_point)
    exits_first_half = await redis.zcount("exits", start, mid_point)
    occupancy_first_half = max(0, entries_first_half - exits_first_half)
    
    entries_second_half = await redis.zcount("entries", mid_point, now)
    exits_second_half = await redis.zcount("exits", mid_point, now)
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
        count = await redis.zcount("entries", point_start, point_end)
        entriesTodaySparkline.append(count)
    
    # Get conversion rate from funnel data
    entered_store = await redis.smembers("funnel:entered_store") or set()
    converted = await redis.smembers("funnel:converted") or set()
    entered_store_count = len(entered_store)
    converted_count = len(converted)
    conversion_rate = (converted_count / entered_store_count * 100) if entered_store_count > 0 else 0
    
    # Get active anomalies count (assuming we store this in Redis)
    active_anomalies = int(await redis.get("active_anomalies") or 0)
    
    return {
        "currentOccupancy": current_occupancy,
        "occupancyTrend": occupancy_trend,
        "totalEntriesToday": total_entries,  # Using window as proxy for today
        "entriesTodaySparkline": entriesTodaySparkline,
        "conversionRate": round(conversion_rate, 2),
        "activeAnomalies": active_anomalies
    }