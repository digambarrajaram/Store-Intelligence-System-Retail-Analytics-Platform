"""
Vercel Serverless Function entry point for Store Intelligence API.

This module adapts the FastAPI application for Vercel's serverless environment.
It handles the differences between a long-running ASGI server (uvicorn) and
Vercel's stateless function model.

Key adaptations:
  - Uses `asgi_handler` from `vercel_asgi` to bridge FastAPI ↔ Vercel
  - Gracefully handles missing Redis/Kafka dependencies (returns degraded responses)
  - Provides mock/fallback data when external services are unavailable
  - Strips lifespan events that require persistent connections
"""

import json
import os
import time
import logging
from datetime import datetime, timezone
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Detect Vercel environment ──────────────────────────────────────────────
IS_VERCEL = os.environ.get("VERCEL", "0") == "1" or os.environ.get("VERCEL_ENV") is not None

# ── Optional Redis import ──────────────────────────────────────────────────
try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    logger.warning("redis.asyncio not available — running in degraded mode")

# ── Optional Kafka import ──────────────────────────────────────────────────
try:
    from aiokafka import AIOKafkaConsumer
    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False
    logger.warning("aiokafka not available — running in degraded mode")

# ── Optional Prometheus import ─────────────────────────────────────────────
try:
    from prometheus_client import make_asgi_app
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    logger.warning("prometheus_client not available — metrics endpoint disabled")

# ── Optional TransactionImporter import ────────────────────────────────────
try:
    from services.transaction_importer import TransactionImporter
    HAS_TRANSACTION_IMPORTER = True
except ImportError:
    HAS_TRANSACTION_IMPORTER = False
    logger.warning("TransactionImporter not available — POS endpoints disabled")


# ── Lifespan (simplified for Vercel) ───────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Simplified lifespan for Vercel serverless environment.
    Redis connection is attempted lazily per-request instead of at startup.
    """
    logger.info("Vercel serverless function starting up")
    app.state.store_ids = ["store_1"]
    app.state.camera_config = {"stores": []}
    yield
    logger.info("Vercel serverless function shutting down")


# ── FastAPI app ────────────────────────────────────────────────────────────

app = FastAPI(
    title="Store Intelligence API (Vercel)",
    description="Multi-store, multi-camera analytics API — Vercel serverless deployment",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Redis connection helper ────────────────────────────────────────────────

async def get_redis(request: Request):
    """Get or create Redis connection for the request."""
    if not HAS_REDIS:
        return None
    if not hasattr(request.app.state, "redis") or request.app.state.redis is None:
        redis_host = os.getenv("REDIS_HOST", os.getenv("UPSTASH_REDIS_HOST", "localhost"))
        redis_port = int(os.getenv("REDIS_PORT", os.getenv("UPSTASH_REDIS_PORT", "6379")))
        redis_password = os.getenv("REDIS_PASSWORD", os.getenv("UPSTASH_REDIS_PASSWORD", ""))
        redis_url = os.getenv("REDIS_URL", f"redis://{redis_host}:{redis_port}")
        
        try:
            if redis_password:
                request.app.state.redis = aioredis.from_url(
                    redis_url, password=redis_password, decode_responses=True, socket_connect_timeout=5
                )
            else:
                request.app.state.redis = aioredis.from_url(
                    redis_url, decode_responses=True, socket_connect_timeout=5
                )
            # Test connection
            await request.app.state.redis.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")
            request.app.state.redis = None
    return request.app.state.redis


# ── Mock data for degraded mode ────────────────────────────────────────────

MOCK_KPI_DATA = {
    "store_id": "store_1",
    "currentOccupancy": 0,
    "occupancyTrend": "stable",
    "totalEntriesToday": 0,
    "entriesTodaySparkline": [],
    "conversionRate": 0,
    "activeAnomalies": 0,
}

MOCK_FUNNEL_DATA = [
    {"step": "Entered Store", "value": 0},
    {"step": "Browsed > 2 min", "value": 0},
    {"step": "Reached Checkout", "value": 0},
    {"step": "Converted", "value": 0},
]

MOCK_OCCUPANCY_HISTORY = []


# ── Health endpoint ────────────────────────────────────────────────────────

@app.get("/health")
async def health(request: Request):
    """Health check endpoint — works without Redis."""
    redis_status = "disabled"
    if HAS_REDIS:
        try:
            r = await get_redis(request)
            if r:
                await r.ping()
                redis_status = "ok"
            else:
                redis_status = "unavailable"
        except Exception:
            redis_status = "error"

    return {
        "status": "healthy",
        "env": os.getenv("VERCEL_ENV", "production"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "redis": redis_status,
            "kafka": "disabled" if not HAS_KAFKA else "configured",
        },
        "version": "2.0.0",
        "deployment": "vercel",
    }


# ── Stores endpoint ────────────────────────────────────────────────────────

@app.get("/api/v1/stores")
async def list_stores(request: Request):
    """List all configured stores."""
    store_ids = getattr(request.app.state, "store_ids", ["store_1"])
    return {"stores": store_ids}


# ── KPI endpoint ───────────────────────────────────────────────────────────

@app.get("/api/v1/kpis")
async def get_kpis(
    request: Request,
    window_minutes: int = Query(60, ge=1, le=1440),
    store_id: str = Query("store_1"),
):
    """Get KPI data — returns mock data if Redis is unavailable."""
    r = await get_redis(request)
    if r is None:
        return {**MOCK_KPI_DATA, "store_id": store_id}

    now = time.time()
    start = now - (window_minutes * 60)

    try:
        total_entries = await r.zcount(f"store:{store_id}:entries", start, now)
        total_exits = await r.zcount(f"store:{store_id}:exits", start, now)
        current_occupancy = max(0, total_entries - total_exits)

        # Occupancy trend
        mid_point = start + (window_minutes * 60) / 2
        entries_first_half = await r.zcount(f"store:{store_id}:entries", start, mid_point)
        exits_first_half = await r.zcount(f"store:{store_id}:exits", start, mid_point)
        occupancy_first_half = max(0, entries_first_half - exits_first_half)

        entries_second_half = await r.zcount(f"store:{store_id}:entries", mid_point, now)
        exits_second_half = await r.zcount(f"store:{store_id}:exits", mid_point, now)
        occupancy_second_half = max(0, entries_second_half - exits_second_half)

        if occupancy_second_half > occupancy_first_half:
            occupancy_trend = 'up'
        elif occupancy_second_half < occupancy_first_half:
            occupancy_trend = 'down'
        else:
            occupancy_trend = 'stable'

        # Sparkline
        sparkline_window = min(30, window_minutes)
        sparkline_start = now - (sparkline_window * 60)
        entries_today_sparkline = []
        for i in range(sparkline_window):
            point_start = sparkline_start + (i * 60)
            point_end = point_start + 60
            count = await r.zcount(f"store:{store_id}:entries", point_start, point_end)
            entries_today_sparkline.append(count)

        # Conversion rate
        entered_store = await r.smembers(f"funnel:store:{store_id}:entered_store") or set()
        converted = await r.smembers(f"funnel:store:{store_id}:converted") or set()
        entered_store_count = len(entered_store)
        converted_count = len(converted)
        conversion_rate = (converted_count / entered_store_count * 100) if entered_store_count > 0 else 0

        # Active anomalies
        active_anomalies = int(await r.get(f"store:{store_id}:active_anomalies") or 0)

        return {
            "store_id": store_id,
            "currentOccupancy": current_occupancy,
            "occupancyTrend": occupancy_trend,
            "totalEntriesToday": total_entries,
            "entriesTodaySparkline": entries_today_sparkline,
            "conversionRate": round(conversion_rate, 2),
            "activeAnomalies": active_anomalies,
        }
    except Exception as e:
        logger.error(f"Error fetching KPIs: {e}")
        return {**MOCK_KPI_DATA, "store_id": store_id}


# ── Store metrics endpoint ─────────────────────────────────────────────────

@app.get("/api/v1/store-metrics")
async def get_store_metrics(
    request: Request,
    window_minutes: int = Query(60, ge=1, le=1440),
    store_id: str = Query("store_1"),
    camera_id: str = Query(None),
):
    """Get store metrics — returns mock data if Redis is unavailable."""
    r = await get_redis(request)
    if r is None:
        return {
            "store_id": store_id,
            "period_start": datetime.now(timezone.utc).isoformat(),
            "period_end": datetime.now(timezone.utc).isoformat(),
            "total_entries": 0,
            "total_exits": 0,
            "current_occupancy": 0,
            "peak_occupancy": 0,
            "avg_dwell_minutes": 0,
            "anomaly_count": 0,
            "camera_fps": 0,
        }

    now = time.time()
    start = now - (window_minutes * 60)

    try:
        entries_key = f"store:{store_id}:entries"
        exits_key = f"store:{store_id}:exits"
        if camera_id and camera_id != "all":
            entries_key = f"store:{store_id}:camera:{camera_id}:entries"
            exits_key = f"store:{store_id}:camera:{camera_id}:exits"

        total_entries = await r.zcount(entries_key, start, now)
        total_exits = await r.zcount(exits_key, start, now)
        current_occupancy = max(0, total_entries - total_exits)

        return {
            "store_id": store_id,
            "period_start": datetime.fromtimestamp(start, tz=timezone.utc).isoformat(),
            "period_end": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "total_entries": total_entries,
            "total_exits": total_exits,
            "current_occupancy": current_occupancy,
            "peak_occupancy": 0,
            "avg_dwell_minutes": 0,
            "anomaly_count": 0,
            "camera_fps": 0,
        }
    except Exception as e:
        logger.error(f"Error fetching store metrics: {e}")
        return {"store_id": store_id, "error": str(e)}


# ── Occupancy history endpoint ─────────────────────────────────────────────

@app.get("/api/v1/occupancy/history")
async def get_occupancy_history(
    request: Request,
    window_minutes: int = Query(60, ge=5, le=1440),
    interval_minutes: int = Query(5, ge=1, le=60),
    store_id: str = Query("store_1"),
    camera_id: str = Query(None),
):
    """Get occupancy history — returns empty data if Redis is unavailable."""
    r = await get_redis(request)
    if r is None:
        return {"store_id": store_id, "camera_id": camera_id or "store", "history": []}

    now = time.time()
    start = now - (window_minutes * 60)
    interval_seconds = interval_minutes * 60
    sample_count = min(int(window_minutes // interval_minutes) + 1, 60)

    try:
        entries_key = f"store:{store_id}:entries"
        exits_key = f"store:{store_id}:exits"
        if camera_id:
            entries_key = f"store:{store_id}:camera:{camera_id}:entries"
            exits_key = f"store:{store_id}:camera:{camera_id}:exits"

        history = []
        for index in range(sample_count):
            point_time = min(start + (index * interval_seconds), now)
            entries = await r.zcount(entries_key, 0, point_time)
            exits = await r.zcount(exits_key, 0, point_time)
            count = max(0, entries - exits)
            history.append({
                "timestamp": datetime.fromtimestamp(point_time, tz=timezone.utc).isoformat(),
                "count": count,
            })

        return {"store_id": store_id, "camera_id": camera_id or "store", "history": history}
    except Exception as e:
        logger.error(f"Error fetching occupancy history: {e}")
        return {"store_id": store_id, "camera_id": camera_id or "store", "history": []}


# ── Funnel endpoint ────────────────────────────────────────────────────────

@app.get("/api/v1/funnel")
async def get_funnel(
    request: Request,
    store_id: str = Query("store_1"),
    camera_id: str = Query(None),
):
    """Get conversion funnel data — returns mock data if Redis is unavailable."""
    r = await get_redis(request)
    if r is None:
        return {"store_id": store_id, "funnel": MOCK_FUNNEL_DATA}

    try:
        prefix = f"funnel:store:{store_id}:"
        if camera_id and camera_id != "all":
            prefix = f"funnel:store:{store_id}:camera:{camera_id}:"

        entered_store = await r.smembers(f"{prefix}entered_store") or set()
        browsed_gt_2min = await r.smembers(f"{prefix}browsed_gt_2min") or set()
        reached_checkout_zone = await r.smembers(f"{prefix}reached_checkout_zone") or set()
        converted = await r.smembers(f"{prefix}converted") or set()

        funnel = [
            {"step": "Entered Store", "value": len(entered_store)},
            {"step": "Browsed > 2 min", "value": len(browsed_gt_2min)},
            {"step": "Reached Checkout", "value": len(reached_checkout_zone)},
            {"step": "Converted", "value": len(converted)},
        ]
        return {"store_id": store_id, "funnel": funnel}
    except Exception as e:
        logger.error(f"Error fetching funnel: {e}")
        return {"store_id": store_id, "funnel": MOCK_FUNNEL_DATA}


# ── Insights endpoints ─────────────────────────────────────────────────────

@app.get("/api/v1/insights/correlation")
async def get_correlation_insights(
    request: Request,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    store_id: str = Query("store_1"),
):
    """Get correlation insights — returns mock data if Redis is unavailable."""
    r = await get_redis(request)
    if r is None:
        return {
            "store_id": store_id,
            "date": date,
            "footfall": 0,
            "transactions": 0,
            "conversion_rate_pct": 0,
            "revenue_per_visitor": 0,
            "avg_basket_gmv": 0,
            "top_performing_category": "",
            "insight": "No data available — Redis not connected.",
        }

    try:
        footfall = int(await r.get(f"store:{store_id}:vision:footfall:{date}") or 0)
        agg_data = await r.hgetall(f"pos:store:{store_id}:aggregates:{date}")

        if not agg_data:
            return {
                "store_id": store_id,
                "date": date,
                "footfall": footfall,
                "transactions": 0,
                "conversion_rate_pct": 0,
                "revenue_per_visitor": 0,
                "avg_basket_gmv": 0,
                "top_performing_category": "",
                "insight": "No POS data found for this date.",
            }

        transactions = int(agg_data.get("total_orders", 0))
        total_gmv = float(agg_data.get("total_gmv", 0))
        avg_basket_gmv = total_gmv / transactions if transactions > 0 else 0.0
        conversion_rate_pct = (transactions / footfall * 100) if footfall > 0 else 0.0
        revenue_per_visitor = total_gmv / footfall if footfall > 0 else 0.0
        top_categories = json.loads(agg_data.get("top_categories", "[]"))
        top_performing_category = top_categories[0] if top_categories else ""

        if conversion_rate_pct > 30:
            insight = f"Conversion rate is {conversion_rate_pct:.2f}% — exceeds the 30% target."
        elif conversion_rate_pct > 20:
            insight = f"Conversion rate is {conversion_rate_pct:.2f}% — above average but below the 30% target."
        else:
            insight = f"Conversion rate is {conversion_rate_pct:.2f}% — below target; review footfall quality or sales strategy."

        return {
            "store_id": store_id,
            "date": date,
            "footfall": footfall,
            "transactions": transactions,
            "conversion_rate_pct": round(conversion_rate_pct, 2),
            "revenue_per_visitor": round(revenue_per_visitor, 2),
            "avg_basket_gmv": round(avg_basket_gmv, 2),
            "top_performing_category": top_performing_category,
            "insight": insight,
        }
    except Exception as e:
        logger.error(f"Error fetching correlation insights: {e}")
        return {"store_id": store_id, "date": date, "error": str(e)}


@app.get("/api/v1/insights/salesperson")
async def get_salesperson_leaderboard(
    request: Request,
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    store_id: str = Query("store_1"),
):
    """Get salesperson leaderboard — returns empty list if Redis is unavailable."""
    if not HAS_TRANSACTION_IMPORTER:
        return []
    r = await get_redis(request)
    if r is None:
        return []

    try:
        ranking = await TransactionImporter(store_id=store_id).get_salesperson_ranking(r, date)
        return ranking or []
    except Exception as e:
        logger.error(f"Error fetching salesperson leaderboard: {e}")
        return []


# ── POS ingest endpoint ────────────────────────────────────────────────────

@app.post("/api/v1/pos/ingest")
async def ingest_pos_data(
    request: Request,
    store_id: str = Query("store_1"),
):
    """Ingest POS data — requires Redis."""
    if not HAS_TRANSACTION_IMPORTER:
        raise HTTPException(status_code=503, detail="TransactionImporter not available")
    r = await get_redis(request)
    if r is None:
        raise HTTPException(status_code=503, detail="Redis not available — cannot ingest POS data")

    try:
        content_type = request.headers.get('content-type', '')

        importer = TransactionImporter(store_id=store_id)

        if content_type.startswith('multipart/form-data'):
            form = await request.form()
            file = form.get('file')
            if not file:
                raise HTTPException(status_code=400, detail="No file uploaded")
            contents = await file.read()
            df = importer.parse_csv(contents)
        elif content_type == 'application/json':
            body = await request.body()
            data = json.loads(body)
            df = importer.parse_json(data)
        else:
            raise HTTPException(status_code=400, detail="Use multipart/form-data or application/json")

        result = await importer.store_transactions(df, r)
        persisted_dates = list(result.get('aggregates', {}).keys())

        response = {
            "store_id": store_id,
            "status": "success",
            "dates": persisted_dates,
            "transactions_processed": result.get('transactions_processed', 0),
            "salesperson_ranking": result.get('salesperson_ranking', {}),
            "aggregates_cached": True,
        }

        if len(persisted_dates) == 1:
            response["date"] = persisted_dates[0]

        return response
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error ingesting POS data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Debug / Simulate endpoint ──────────────────────────────────────────────

@app.post("/api/v1/simulate")
async def simulate(
    request: Request,
    entries: int = Query(10),
    exits: int = Query(5),
    anomalies: int = Query(2),
    dwell_seconds: int = Query(120),
    store_id: str = Query("store_1"),
    camera_id: str = Query("camera_0"),
):
    """Simulate detection data — requires Redis."""
    r = await get_redis(request)
    if r is None:
        raise HTTPException(status_code=503, detail="Redis not available — cannot simulate data")

    now = time.time()
    start_time = now - 600

    try:
        for i in range(entries):
            ts = start_time + (i / max(entries, 1)) * 600
            await r.zadd(f'store:{store_id}:camera:{camera_id}:entries', {f'entry:{int(now)}:{i}': ts})
            await r.zadd(f'store:{store_id}:entries', {f'{camera_id}:entry:{int(now)}:{i}': ts})

        for i in range(exits):
            ts = start_time + (i / max(exits, 1)) * 600
            await r.zadd(f'store:{store_id}:camera:{camera_id}:exits', {f'exit:{int(now)}:{i}': ts})
            await r.zadd(f'store:{store_id}:exits', {f'{camera_id}:exit:{int(now)}:{i}': ts})

        await r.incrby(f'store:{store_id}:camera:{camera_id}:anomaly_count', anomalies)

        return {
            "status": "simulation_complete",
            "store_id": store_id,
            "camera_id": camera_id,
            "entries_added": entries,
            "exits_added": exits,
            "anomalies_added": anomalies,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error simulating data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Pipeline status endpoint ───────────────────────────────────────────────

@app.get("/api/v1/pipeline/status")
async def pipeline_status(
    request: Request,
    store_id: str = Query("store_1"),
    camera_id: str = Query("camera_0"),
):
    """Get pipeline status — requires Redis."""
    r = await get_redis(request)
    if r is None:
        return {
            "store_id": store_id,
            "camera_id": camera_id,
            "frames_processed": 0,
            "last_frame_id": 0,
            "unique_tracks_seen": 0,
            "events_published": 0,
            "worker_last_heartbeat": None,
        }

    try:
        return {
            "store_id": store_id,
            "camera_id": camera_id,
            "frames_processed": int(await r.get('cv:pipeline:frames_processed') or 0),
            "last_frame_id": int(await r.get('cv:pipeline:last_frame_id') or 0),
            "unique_tracks_seen": int(await r.get('cv:pipeline:unique_tracks_seen') or 0),
            "events_published": int(await r.get('cv:pipeline:events_published') or 0),
            "worker_last_heartbeat": await r.get('cv:pipeline:worker_last_heartbeat'),
        }
    except Exception as e:
        logger.error(f"Error fetching pipeline status: {e}")
        return {"error": str(e)}


# ── Vercel handler ─────────────────────────────────────────────────────────
# Vercel's Python runtime natively supports ASGI apps.
# Export the FastAPI `app` directly — Vercel will detect and wrap it.
# The `handler` alias is also provided for compatibility with vercel_asgi/mangum.

try:
    from vercel_asgi import AsgiHandler
    handler = AsgiHandler(app)
except ImportError:
    try:
        from mangum import Mangum
        handler = Mangum(app, lifespan="off")
    except ImportError:
        # Fallback: export the FastAPI app directly (Vercel natively supports ASGI)
        handler = app
