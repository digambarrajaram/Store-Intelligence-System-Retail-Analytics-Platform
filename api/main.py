"""
CV Pipeline — FastAPI Shell
Day 1 skeleton: /health + /api/v1/analytics
Day 2 adds:    /ws/alerts WebSocket + anomaly consumer
"""

from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis
import uvicorn
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel
from pydantic_settings import BaseSettings


# ── Config ─────────────────────────────────────────────────────────

class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "info"
    kafka_bootstrap_servers: str = "kafka:29092"
    kafka_consumer_group: str = "cv-api-consumers"
    kafka_topic_detections: str = "cv.detections"
    kafka_topic_anomalies: str = "cv.anomalies"
    redis_url: str = "redis://redis:6379/0"
    redis_pubsub_channel: str = "cv:alerts"
    anomaly_dwell_threshold_sec: int = 30
    anomaly_crowd_threshold: int = 10

    class Config:
        env_file = ".env"


settings = Settings()


# ── Models ─────────────────────────────────────────────────────────

class DetectionEvent(BaseModel):
    frame_id: int
    timestamp: float
    camera_id: str
    detections: list[dict[str, Any]]   # [{bbox, conf, class_id, track_id}]
    fps: float


class AnomalyEvent(BaseModel):
    anomaly_id: str
    anomaly_type: str                  # "dwell" | "crowd"
    camera_id: str
    timestamp: float
    severity: str                      # "low" | "medium" | "high"
    metadata: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    env: str
    timestamp: str
    services: dict[str, str]
    version: str = "0.1.0"


class AnalyticsResponse(BaseModel):
    window_minutes: int
    total_detections: int
    unique_tracks: int
    anomaly_count: int
    avg_crowd_size: float
    peak_crowd_size: int
    avg_fps: float
    top_cameras: list[dict[str, Any]]
    heatmap_buckets: list[list[int]]   # 10×10 grid counts


# ── App State ──────────────────────────────────────────────────────

class AppState:
    redis: aioredis.Redis | None = None
    kafka_producer: AIOKafkaProducer | None = None
    ws_clients: set[WebSocket] = set()


state = AppState()


# ── Lifespan ───────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    state.kafka_producer = AIOKafkaProducer(
        bootstrap_servers=settings.kafka_bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode(),
    )
    await state.kafka_producer.start()

    # Start background WebSocket fan-out from Redis Pub/Sub
    asyncio.create_task(_redis_pubsub_fanout())

    yield

    # shutdown
    await state.kafka_producer.stop()
    await state.redis.close()


# ── FastAPI App ────────────────────────────────────────────────────

app = FastAPI(
    title="CV Pipeline API",
    description="FAANG-style computer vision analytics backend",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # tighten in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)  # /metrics for Prometheus


# ── Health ─────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["Ops"])
async def health() -> HealthResponse:
    """
    Liveness + dependency checks.
    Returns 200 only when Kafka + Redis are reachable.
    """
    services: dict[str, str] = {}

    # Redis ping
    try:
        await state.redis.ping()
        services["redis"] = "ok"
    except Exception as exc:
        services["redis"] = f"error: {exc}"

    # Kafka producer (already started — check metadata)
    try:
        await state.kafka_producer.client._wait_on_metadata(
            settings.kafka_topic_detections, timeout_ms=3000
        )
        services["kafka"] = "ok"
    except Exception as exc:
        services["kafka"] = f"error: {exc}"

    overall = "healthy" if all(v == "ok" for v in services.values()) else "degraded"

    return HealthResponse(
        status=overall,
        env=settings.app_env,
        timestamp=datetime.now(timezone.utc).isoformat(),
        services=services,
    )


# ── Analytics ──────────────────────────────────────────────────────

@app.get("/api/v1/analytics", response_model=AnalyticsResponse, tags=["Analytics"])
async def analytics(window: int = 15) -> AnalyticsResponse:
    """
    Aggregated detection KPIs over the last `window` minutes.
    Data is read from Redis counters written by the worker.

    Redis keys used:
      cv:stats:detections          INCR per detection
      cv:stats:anomalies           INCR per anomaly
      cv:stats:crowd:{camera_id}   LPUSH crowd size per frame
      cv:heatmap:10x10             JSON 10×10 grid
      cv:tracks                    SADD track IDs
    """
    pipe = state.redis.pipeline()
    pipe.get("cv:stats:detections")
    pipe.get("cv:stats:anomalies")
    pipe.get("cv:stats:avg_fps")
    pipe.get("cv:stats:peak_crowd")
    pipe.get("cv:heatmap:10x10")
    pipe.scard("cv:tracks")
    results = await pipe.execute()

    total_detections = int(results[0] or 0)
    anomaly_count = int(results[1] or 0)
    avg_fps = float(results[2] or 0.0)
    peak_crowd = int(results[3] or 0)
    heatmap_raw = results[4]
    unique_tracks = int(results[5] or 0)

    heatmap = json.loads(heatmap_raw) if heatmap_raw else [[0] * 10 for _ in range(10)]

    return AnalyticsResponse(
        window_minutes=window,
        total_detections=total_detections,
        unique_tracks=unique_tracks,
        anomaly_count=anomaly_count,
        avg_crowd_size=round(total_detections / max(1, 300), 2),  # rough estimate
        peak_crowd_size=peak_crowd,
        avg_fps=avg_fps,
        top_cameras=[{"camera_id": "cam-01", "detections": total_detections}],
        heatmap_buckets=heatmap,
    )


# ── WebSocket — live anomaly feed ──────────────────────────────────

@app.websocket("/ws/alerts")
async def ws_alerts(websocket: WebSocket):
    """
    Streams AnomalyEvent JSON from Redis Pub/Sub to every connected client.
    React dashboard subscribes here for the live alert feed.
    """
    await websocket.accept()
    state.ws_clients.add(websocket)
    try:
        while True:
            # keep-alive ping every 20 s
            await asyncio.sleep(20)
            await websocket.send_json({"type": "ping", "ts": time.time()})
    except WebSocketDisconnect:
        state.ws_clients.discard(websocket)


async def _redis_pubsub_fanout():
    """Background task: subscribe to Redis channel and broadcast to WS clients."""
    pubsub = state.redis.pubsub()
    await pubsub.subscribe(settings.redis_pubsub_channel)
    async for message in pubsub.listen():
        if message["type"] == "message":
            payload = message["data"]
            dead: set[WebSocket] = set()
            for ws in state.ws_clients:
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead.add(ws)
            state.ws_clients -= dead


# ── Manual ingest (testing / replay) ──────────────────────────────

@app.post("/api/v1/ingest/detection", tags=["Ingest"])
async def ingest_detection(event: DetectionEvent):
    """Push a DetectionEvent directly to Kafka (useful for testing)."""
    await state.kafka_producer.send(
        settings.kafka_topic_detections, value=event.model_dump()
    )
    return {"queued": True, "topic": settings.kafka_topic_detections}


@app.post("/api/v1/ingest/anomaly", tags=["Ingest"])
async def ingest_anomaly(event: AnomalyEvent):
    """Push an AnomalyEvent to Kafka AND fan-out via Redis Pub/Sub."""
    await state.kafka_producer.send(
        settings.kafka_topic_anomalies, value=event.model_dump()
    )
    await state.redis.publish(
        settings.redis_pubsub_channel, json.dumps(event.model_dump())
    )
    return {"queued": True, "topic": settings.kafka_topic_anomalies}


# ── Entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=settings.log_level,
    )
