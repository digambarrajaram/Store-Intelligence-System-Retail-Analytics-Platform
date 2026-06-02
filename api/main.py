import os
import time
import asyncio
from redis import Redis
from redis import asyncio as aioredis  # Native Redis asyncio module
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from kafka_consumer import consume_kafka

from websocket import (
    init_websocket,
    cleanup_websocket,
    router as websocket_router,
    ws_router
)

from routers import analytics, insights, pos


app = FastAPI(
    title="Store Intelligence System API",
    version="0.1.0"
)

# 1. Global Configuration Layout: CORS Middleware Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Prometheus Metric Hook (Must be global, outside of startup)
Instrumentator().instrument(app).expose(app)

# 3. Router Registrations 
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(insights.router, prefix="/api/v1")
app.include_router(pos.router, prefix="/api/v1")
app.include_router(websocket_router, prefix="/api/v1")
app.include_router(ws_router)

# 4. Mandatory Health Check Route (Fixes Docker Compose 404 Unhealthy Crash)
@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    redis_status = "unknown"
    kafka_status = "unknown"
    try:
        if hasattr(app.state, "redis"):
            redis_ping = await app.state.redis.ping()
            redis_status = "ok" if redis_ping else "error"
    except Exception:
        redis_status = "error"

    try:
        if hasattr(app.state, "kafka_task"):
            kafka_status = "ok" if not app.state.kafka_task.done() else "error"
    except Exception:
        kafka_status = "error"

    return {
        "status": "healthy" if redis_status == "ok" and kafka_status == "ok" else "degraded",
        "env": os.getenv("ENV", "production"),
        "timestamp": int(time.time()),
        "services": {
            "redis": redis_status,
            "kafka": kafka_status
        },
        "version": "0.1.0"
    }

# 5. Lifespan Startup Mechanics
@app.on_event("startup")
async def startup_event():
    print("Initializing background data streaming interfaces...")
    
    # Fetch environment parameters securely
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    
    # Establish and bind the connection pool to app.state
    print(f"Connecting to Redis cluster at {redis_host}:{redis_port}...")
    app.state.redis = aioredis.from_url(
        f"redis://{redis_host}:{redis_port}", 
        encoding="utf-8", 
        decode_responses=True
    )
    app.state.sync_redis = Redis(
        host=redis_host,
        port=redis_port,
        db=0,
        decode_responses=True
    )
    
    # 🟢 FIXED: Removed "await" because init_websocket is a regular synchronous function
    init_websocket(app)

    app.state.kafka_task = asyncio.create_task(
        consume_kafka(app)
    )

    print("Application startup sequence finalized.")

@app.on_event("shutdown")
async def shutdown_event():
    print("Closing backend persistent state infrastructure...")
    await cleanup_websocket(app)
    if hasattr(app.state, "kafka_task"):
        app.state.kafka_task.cancel()
        try:
            await app.state.kafka_task
        except asyncio.CancelledError:
            pass
    if hasattr(app.state, "redis"):
        await app.state.redis.close()
    if hasattr(app.state, "sync_redis"):
        app.state.sync_redis.close()
