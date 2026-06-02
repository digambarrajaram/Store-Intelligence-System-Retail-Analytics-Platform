# EXACT CODE FIXES - Production-Ready Implementation

## CRITICAL FIX #1: Redis Connection Leaks in All Routers

### File: api/routers/analytics.py

```python
# ✅ BEFORE (BROKEN)
from fastapi import APIRouter, Depends, Query
from redis import Redis
import datetime
import time
import os

from services.conversion_engine import ConversionEngine

router = APIRouter()

def get_redis():  # ❌ Creates NEW connection per request
    return Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        db=0,
        decode_responses=True
    )

@router.get("/metrics")
async def get_metrics(
    window_minutes: int = Query(60, ge=1, le=1440),
    redis: Redis = Depends(get_redis)  # ❌ Leaks connection
):
    # ... use redis

# ✅ AFTER (FIXED)
from fastapi import APIRouter, Query, Request
import datetime
import time

from services.conversion_engine import ConversionEngine

router = APIRouter()

@router.get("/metrics")
async def get_metrics(
    window_minutes: int = Query(60, ge=1, le=1440),
    request: Request
):
    """Use app.state.redis instead of creating new connection"""
    redis = request.app.state.redis  # ✅ Reuse pooled connection
    
    # ... rest of function same
```

### File: api/routers/insights.py

```python
# ✅ BEFORE (BROKEN)
from fastapi import APIRouter, HTTPException, Query, Depends
from redis import Redis
from datetime import datetime

def get_redis():  # ❌ Creates NEW connection per request
    return Redis(
        host=os.getenv('REDIS_HOST', 'redis'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0,
        decode_responses=True
    )

@router.get("/insights/correlation")
async def get_correlation_insights(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    r: Redis = Depends(get_redis)  # ❌ Leaks connection
):

# ✅ AFTER (FIXED)
from fastapi import APIRouter, HTTPException, Query, Request
from datetime import datetime
import json

@router.get("/insights/correlation")
async def get_correlation_insights(
    date: str = Query(..., description="Date in YYYY-MM-DD format"),
    request: Request
):
    """Use app.state.redis instead of creating new connection"""
    r = request.app.state.redis  # ✅ Reuse pooled connection
    
    try:
        datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Expected YYYY-MM-DD")

    # ... rest of function same
```

### File: api/routers/pos.py

```python
# ✅ BEFORE (BROKEN)
from fastapi import APIRouter, Request, UploadFile, HTTPException, Depends
from redis import Redis

def get_redis():  # ❌ Creates NEW connection per request
    return Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0,
        decode_responses=True
    )

@router.post("/pos/ingest")
async def ingest_pos_data(
    request: Request,
    r: Redis = Depends(get_redis)  # ❌ Leaks connection
):

# ✅ AFTER (FIXED)
from fastapi import APIRouter, Request, UploadFile, HTTPException
import json

@router.post("/pos/ingest")
async def ingest_pos_data(request: Request):
    """Use app.state.redis instead of creating new connection"""
    r = request.app.state.redis  # ✅ Reuse pooled connection
    
    content_type = request.headers.get('content-type', '')
    importer = TransactionImporter()

    # ... rest of function same
```

### File: api/routers/debug.py

```python
# ✅ BEFORE (BROKEN)
from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
import datetime
import time
import json
import os

def get_redis():  # ❌ Creates NEW connection per request
    return Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=0,
        decode_responses=True
    )

@router.post("/simulate", tags=["Debug"])
async def simulate(
    entries: int,
    exits: int,
    anomalies: int,
    dwell_seconds: int,
    redis: Redis = Depends(get_redis)  # ❌ Leaks connection
):

# ✅ AFTER (FIXED)
from fastapi import APIRouter, Request
import datetime
import time
import json

@router.post("/simulate", tags=["Debug"])
async def simulate(
    entries: int,
    exits: int,
    anomalies: int,
    dwell_seconds: int,
    request: Request
):
    """Use app.state.redis instead of creating new connection"""
    redis = request.app.state.redis  # ✅ Reuse pooled connection
    
    # ... rest of function same
```

---

## CRITICAL FIX #2: FastAPI Startup - Kafka Consumer + WebSocket

### File: api/main.py

```python
# ✅ BEFORE (BROKEN)
import os
import time
import asyncio
from redis import asyncio as aioredis
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

@app.on_event("startup")
async def startup_event():
    print("Initializing background data streaming interfaces...")
    
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    
    print(f"Connecting to Redis cluster at {redis_host}:{redis_port}...")
    app.state.redis = aioredis.from_url(
        f"redis://{redis_host}:{redis_port}", 
        encoding="utf-8", 
        decode_responses=True
    )
    
    init_websocket(app)  # ❌ Not starting pub/sub listener

    app.state.kafka_task = asyncio.create_task(
        consume_kafka(app)  # ❌ No error handling or validation
    )

    print("Application startup sequence finalized.")

@app.on_event("shutdown")
async def shutdown_event():
    print("Closing backend persistent state infrastructure...")
    await cleanup_websocket(app)
    if hasattr(app.state, "redis"):
        await app.state.redis.close()


# ✅ AFTER (FIXED)
import os
import time
import asyncio
from contextlib import asynccontextmanager
from redis import asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from kafka_consumer import consume_kafka

from websocket import (
    init_websocket,
    cleanup_websocket,
    router as websocket_router,
    ws_router,
    manager,
    pubsub_listener
)

# Global state for background tasks
_background_tasks = []

async def validate_redis_connection(redis_client):
    """Validate Redis is actually working"""
    try:
        await redis_client.ping()
        return True
    except Exception as e:
        print(f"ERROR: Redis validation failed: {e}")
        return False

async def validate_kafka_bootstrap():
    """Pre-flight check that Kafka is reachable"""
    try:
        from aiokafka import AIOKafkaProducer
        producer = AIOKafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
            request_timeout_ms=5000
        )
        await producer.start()
        await producer.stop()
        return True
    except Exception as e:
        print(f"WARNING: Kafka pre-check failed: {e}")
        return False

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown"""
    
    # ===== STARTUP =====
    print("[STARTUP] Initializing Store Intelligence API...")
    
    # 1. Initialize Redis with validation
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = int(os.getenv("REDIS_PORT", 6379))
    
    print(f"[STARTUP] Connecting to Redis at {redis_host}:{redis_port}...")
    app.state.redis = aioredis.from_url(
        f"redis://{redis_host}:{redis_port}", 
        encoding="utf-8", 
        decode_responses=True,
        socket_connect_timeout=10,
        socket_keepalive=True,
        socket_keepalive_intvl=30,
    )
    
    # Validate Redis connection
    if not await validate_redis_connection(app.state.redis):
        raise RuntimeError("Failed to connect to Redis - cannot start application")
    print("[STARTUP] ✅ Redis connected and validated")
    
    # 2. Pre-check Kafka (warn but don't fail)
    kafka_ok = await validate_kafka_bootstrap()
    if not kafka_ok:
        print("[STARTUP] ⚠️  Kafka pre-check failed - will attempt to connect during runtime")
    else:
        print("[STARTUP] ✅ Kafka pre-check passed")
    
    # 3. Initialize WebSocket with manager.redis
    print("[STARTUP] Initializing WebSocket manager...")
    init_websocket(app)
    print("[STARTUP] ✅ WebSocket manager initialized")
    
    # 4. Start WebSocket pub/sub listener as background task
    print("[STARTUP] Starting WebSocket pub/sub listener...")
    try:
        pubsub_task = asyncio.create_task(pubsub_listener(app.state.redis))
        _background_tasks.append(pubsub_task)
        print("[STARTUP] ✅ WebSocket pub/sub listener started")
    except Exception as e:
        print(f"[STARTUP] ❌ Failed to start pub/sub listener: {e}")
        raise RuntimeError("Failed to initialize WebSocket pub/sub") from e
    
    # 5. Start Kafka consumer as background task with error handling
    print("[STARTUP] Starting Kafka consumer...")
    try:
        consumer_task = asyncio.create_task(consume_kafka(app))
        _background_tasks.append(consumer_task)
        
        # Give consumer 5 seconds to start and fail fast if config is wrong
        await asyncio.sleep(5)
        if consumer_task.done():
            # If task finished already, it likely failed
            try:
                consumer_task.result()  # This will raise the exception
            except Exception as e:
                print(f"[STARTUP] ❌ Kafka consumer failed to start: {e}")
                raise RuntimeError(f"Kafka consumer failed: {e}") from e
        
        print("[STARTUP] ✅ Kafka consumer started")
    except Exception as e:
        print(f"[STARTUP] ❌ Failed to start Kafka consumer: {e}")
        raise RuntimeError("Failed to initialize Kafka consumer") from e
    
    print("[STARTUP] ✅ Application startup complete")
    
    yield
    
    # ===== SHUTDOWN =====
    print("[SHUTDOWN] Closing application resources...")
    
    # 1. Cancel all background tasks
    for task in _background_tasks:
        if not task.done():
            task.cancel()
    
    # Wait for tasks to complete (with timeout)
    if _background_tasks:
        try:
            await asyncio.wait_for(
                asyncio.gather(*_background_tasks, return_exceptions=True),
                timeout=10
            )
        except asyncio.TimeoutError:
            print("[SHUTDOWN] ⚠️  Background tasks did not complete within timeout")
        except Exception as e:
            print(f"[SHUTDOWN] Warning during task cancellation: {e}")
    
    # 2. Cleanup WebSocket
    try:
        await cleanup_websocket(app)
        print("[SHUTDOWN] ✅ WebSocket cleaned up")
    except Exception as e:
        print(f"[SHUTDOWN] Warning during WebSocket cleanup: {e}")
    
    # 3. Close Redis
    if hasattr(app.state, "redis") and app.state.redis:
        try:
            await app.state.redis.close()
            print("[SHUTDOWN] ✅ Redis closed")
        except Exception as e:
            print(f"[SHUTDOWN] Warning during Redis close: {e}")
    
    print("[SHUTDOWN] ✅ Application shutdown complete")


# Create app with lifespan
app = FastAPI(
    title="Store Intelligence System API",
    version="0.1.0",
    lifespan=lifespan
)

# Rest of middleware and routers remain the same...
```

---

## CRITICAL FIX #3: Kafka Consumer - Complete Truncated Code

### File: api/kafka_consumer.py

```python
# ✅ COMPLETE IMPLEMENTATION
import json
import time
import os
import logging

from aiokafka import AIOKafkaConsumer

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_CONSUMER_GROUP = os.getenv("KAFKA_CONSUMER_GROUP", "cv-api-consumers")
KAFKA_TOPIC_DETECTIONS = os.getenv("KAFKA_TOPIC_DETECTIONS", "cv.detections")


async def consume_kafka(app):
    """
    Consume detection events from Kafka and update Redis with metrics.
    
    Handles:
    - Entry/exit tracking
    - Dwell time calculation
    - Occupancy monitoring
    - Graceful reconnection
    """
    
    logger.info(f"[KAFKA] Starting Kafka consumer (group={KAFKA_CONSUMER_GROUP})")
    
    consumer = None
    retry_count = 0
    max_retries = 10
    base_delay = 2
    
    while retry_count < max_retries:
        try:
            consumer = AIOKafkaConsumer(
                KAFKA_TOPIC_DETECTIONS,
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                group_id=KAFKA_CONSUMER_GROUP,
                auto_offset_reset="latest",
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                session_timeout_ms=30000,
                request_timeout_ms=60000,
                connections_max_idle_ms=540000,
            )
            
            logger.info("[KAFKA] Consumer created, starting...")
            await consumer.start()
            logger.info("[KAFKA] ✅ Kafka consumer connected successfully")
            retry_count = 0  # Reset retry counter on successful connection
            
        except Exception as e:
            retry_count += 1
            delay = base_delay ** min(retry_count, 5)  # Exponential backoff, max 32s
            logger.error(
                f"[KAFKA] Connection attempt {retry_count}/{max_retries} failed: {e}. "
                f"Retrying in {delay}s..."
            )
            if retry_count >= max_retries:
                logger.error("[KAFKA] ❌ Max retries exceeded, consumer failed")
                raise RuntimeError(f"Failed to connect to Kafka after {max_retries} attempts") from e
            await asyncio.sleep(delay)
            continue
        
        # Successfully connected - start consuming
        redis = app.state.redis
        frame_count = 0
        
        try:
            async for message in consumer:
                try:
                    frame_count += 1
                    event = message.value
                    detections = event.get("detections", [])
                    now = time.time()
                    
                    # Track current and previous tracks
                    current_tracks = set()
                    for det in detections:
                        track_id = str(det["track_id"])
                        current_tracks.add(track_id)
                        
                        # Add to sorted set for entry tracking
                        exists = await redis.zscore("entries", track_id)
                        if exists is None:
                            await redis.zadd("entries", {track_id: now})
                    
                    # Check for exits (tracks that were active but are now gone)
                    stored_tracks = await redis.smembers("active_tracks")
                    stored_tracks = set(stored_tracks) if stored_tracks else set()
                    exited_tracks = stored_tracks - current_tracks
                    
                    for track_id in exited_tracks:
                        # Check if we already recorded this exit
                        already_exited = await redis.zscore("exits", track_id)
                        if already_exited is None:
                            # Record the exit
                            await redis.zadd("exits", {track_id: now})
                            
                            # Calculate dwell time
                            entry_time = await redis.zscore("entries", track_id)
                            if entry_time:
                                dwell_time = now - float(entry_time)
                                await redis.hset("dwell_times", track_id, dwell_time)
                    
                    # Update active tracks for next iteration
                    await redis.delete("active_tracks")
                    if current_tracks:
                        await redis.sadd("active_tracks", *list(current_tracks))
                    
                    # Update occupancy metrics
                    occupancy = len(current_tracks)
                    await redis.set("current_occupancy", occupancy)
                    
                    # Check if peak occupancy needs updating
                    current_peak = int(await redis.get("peak_occupancy") or 0)
                    if occupancy > current_peak:
                        await redis.set("peak_occupancy", occupancy)
                    
                    # Update FPS
                    fps = event.get("fps", 0)
                    await redis.set("camera_fps", fps)
                    
                    # Update last updated timestamp
                    await redis.set("metrics:last_updated", now)
                    
                    # Log every 100 frames
                    if frame_count % 100 == 0:
                        logger.debug(
                            f"[KAFKA] Processed {frame_count} messages. "
                            f"Current occupancy: {occupancy}, Peak: {current_peak}"
                        )
                
                except json.JSONDecodeError as e:
                    logger.error(f"[KAFKA] Failed to decode message: {e}")
                except Exception as e:
                    logger.error(f"[KAFKA] Error processing message: {e}")
                    # Continue consuming even if one message fails
        
        except asyncio.CancelledError:
            logger.info("[KAFKA] Consumer task cancelled (shutdown)")
            break
        except Exception as e:
            logger.error(f"[KAFKA] Consumer loop error: {e}")
            retry_count += 1
            if retry_count >= max_retries:
                raise RuntimeError(f"Kafka consumer failed permanently: {e}") from e
            delay = base_delay ** min(retry_count, 5)
            logger.info(f"[KAFKA] Reconnecting in {delay}s...")
            await asyncio.sleep(delay)
        finally:
            if consumer:
                try:
                    await consumer.stop()
                    logger.info("[KAFKA] Consumer stopped")
                except Exception as e:
                    logger.error(f"[KAFKA] Error stopping consumer: {e}")


import asyncio
```

---

## CRITICAL FIX #4: WebSocket - Initialize Pub/Sub Listener

### File: api/websocket.py

```python
# ✅ ADD THIS FUNCTION (Find the existing code and add this function)

async def pubsub_listener(redis_conn: aioredis.Redis):
    """
    Listen to Redis pub/sub channel and broadcast anomalies to WebSocket clients.
    This is a background task that runs for the lifetime of the application.
    """
    pubsub = redis_conn.pubsub()
    await pubsub.subscribe("anomaly_alerts")
    
    logger.info("[WS] Pub/sub listener started, subscribed to anomaly_alerts")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    logger.debug(f"[WS] Received anomaly alert: {data.get('anomaly_id', 'unknown')}")
                    
                    # Store for catch-up
                    await store_anomaly_for_catchup(redis_conn, data)
                    
                    # Broadcast to all connected WebSocket clients
                    await manager.broadcast_anomaly(data)
                    
                except json.JSONDecodeError as e:
                    logger.error(f"[WS] Failed to decode pub/sub message: {e}")
                except Exception as e:
                    logger.error(f"[WS] Error processing pub/sub message: {e}")
    
    except asyncio.CancelledError:
        logger.info("[WS] Pub/sub listener cancelled (shutdown)")
    except Exception as e:
        logger.error(f"[WS] Pub/sub listener error: {e}")
    finally:
        try:
            await pubsub.unsubscribe("anomaly_alerts")
            await pubsub.close()
            logger.info("[WS] Pub/sub connection closed")
        except Exception as e:
            logger.warning(f"[WS] Error closing pubsub: {e}")


async def store_anomaly_for_catchup(redis_conn: aioredis.Redis, anomaly: dict):
    """Store anomaly in Redis list for new clients to catch up"""
    try:
        await redis_conn.lpush("recent_anomalies", json.dumps(anomaly))
        await redis_conn.ltrim("recent_anomalies", 0, 9)  # Keep only last 10
    except Exception as e:
        logger.error(f"[WS] Failed to store anomaly for catchup: {e}")


# ✅ ALSO UPDATE init_websocket() to NOT be sync:

async def init_websocket(app: FastAPI) -> None:
    """Initialize WebSocket manager with Redis connection"""
    manager.redis = app.state.redis
    logger.info("[WS] WebSocket manager initialized with Redis")


# ✅ Update cleanup_websocket() to handle background tasks:

async def cleanup_websocket(app: FastAPI) -> None:
    """Cleanup WebSocket connections and stop ping task"""
    # Ping task will be cancelled by lifespan handler
    # Just disconnect all active connections
    for connection in list(manager.active_connections):
        try:
            manager.disconnect(connection)
        except Exception as e:
            logger.warning(f"[WS] Error disconnecting: {e}")
    
    logger.info("[WS] WebSocket cleanup complete")
```

---

## CRITICAL FIX #5: Kafka Configuration - Fix Port

### File: api/main.py (Settings class)

```python
# ❌ BEFORE
class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "info"
    kafka_bootstrap_servers: str = "kafka:29092"  # ❌ WRONG!
    kafka_consumer_group: str = "cv-api-consumers"
    kafka_topic_detections: str = "cv.detections"
    kafka_topic_anomalies: str = "cv.anomalies"
    redis_url: str = "redis://redis:6379/0"
    redis_pubsub_channel: str = "cv:alerts"

# ✅ AFTER
class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "info"
    kafka_bootstrap_servers: str = "kafka:9092"  # ✅ CORRECT!
    kafka_consumer_group: str = "cv-api-consumers"
    kafka_topic_detections: str = "cv.detections"
    kafka_topic_anomalies: str = "cv.anomalies"
    redis_url: str = "redis://redis:6379/0"
    redis_pubsub_channel: str = "cv:alerts"
    
    class Config:
        env_file = ".env"
```

---

## CRITICAL FIX #6: Docker Compose - Environment Variables

### File: docker-compose.yml

```yaml
# ❌ BEFORE
  dashboard:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
      args:
        VITE_API_URL: ${VITE_API_URL:-}        # ❌ Empty default!
        VITE_WS_URL: ${VITE_WS_URL:-}          # ❌ Empty default!
    environment:
      - VITE_API_URL=                          # ❌ Overrides with empty!
      - VITE_WS_URL=

# ✅ AFTER
  dashboard:
    build:
      context: ./dashboard
      dockerfile: Dockerfile
      args:
        VITE_API_URL: ${VITE_API_URL:-http://localhost:8000}  # ✅ Good default
        VITE_WS_URL: ${VITE_WS_URL:-ws://localhost:8000}      # ✅ Good default
    image: store-intelligence-dashboard:latest
    hostname: dashboard
    container_name: dashboard
    restart: unless-stopped
    depends_on:
      api:
        condition: service_healthy
    ports:
      - "3000:3000"
    environment:
      - VITE_API_URL=${VITE_API_URL:-http://api:8000}  # ✅ Docker network default
      - VITE_WS_URL=${VITE_WS_URL:-ws://api:8000}      # ✅ Docker network default
    healthcheck:
      test: ["CMD", "wget", "-q", "--spider", "http://localhost:3000/"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
    networks:
      - store-net
```

---

## HIGH PRIORITY FIX #1: Complete Anomaly Detector

### File: detection/anomaly_detector.py

See complete replacement file in CRITICAL FIX section at end of this document.

---

## HIGH PRIORITY FIX #2: Kafka Consumer Configuration

### File: api/kafka_consumer.py - Replace hardcoded settings

```python
# See CRITICAL FIX #3 above for complete implementation
# Key changes:
# - Use environment variables for all configuration
# - Add exponential backoff reconnection logic
# - Add proper error handling and logging
```

---

## HIGH PRIORITY FIX #3: Worker - Better Error Handling

### File: worker/worker.py

```python
# ✅ UPDATE THE KAFKA PRODUCER INITIALIZATION

producer = None
for attempt in range(10):
    try:
        producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await producer.start()
        print(f"Kafka producer connected on attempt {attempt + 1}")
        break
    except Exception as e:
        print(f"Kafka connection attempt {attempt + 1} failed: {e}")
        if attempt < 9:  # Not the last attempt
            await asyncio.sleep(5)
        else:
            print("ERROR: Could not connect to Kafka after 10 attempts. Exiting.")
            await producer.stop() if producer else None
            # ✅ EXIT HERE - Don't continue with None producer
            sys.exit(1)

# ✅ Then later in the code - validate producer is not None
if producer is None:
    print("ERROR: Producer is None, cannot continue")
    sys.exit(1)

# ✅ ALSO ADD ERROR HANDLING FOR CRITICAL SERVICES
if alert_engine is None and processor is not None:
    print("WARNING: AlertEngine failed to initialize, continuing without alerts")
    # This is OK - alerts are optional

if processor is None:
    print("ERROR: VideoProcessor required but failed to initialize")
    sys.exit(1)
```

---

## HIGH PRIORITY FIX #4: Health Checks

### File: docker-compose.yml

```yaml
# ✅ BEFORE
api:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 40s

# ✅ AFTER - Add timeout and make it non-blocking
api:
  healthcheck:
    test: ["CMD", "curl", "-f", "--connect-timeout", "5", "--max-time", "10", "http://localhost:8000/health"]
    interval: 30s
    timeout: 15s
    retries: 5
    start_period: 60s  # More time for startup

# ✅ Worker healthcheck - add timeout to Redis call
worker:
  healthcheck:
    test: ["CMD", "timeout", "5", "python", "-c", "import redis; r=redis.Redis(host='redis',port=6379,socket_connect_timeout=3,socket_keepalive=True); val=r.get('worker.alive'); exit(0 if val == '1' else 1)"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 60s
```

---

## MEDIUM PRIORITY FIX #1: Consistent Python Version

### File: Dockerfile (main)

```dockerfile
# ❌ BEFORE
FROM python:3.10-slim

# ✅ AFTER
FROM python:3.11-slim
```

### File: Dockerfile.api

```dockerfile
# ❌ BEFORE
FROM python:3.10-slim

# ✅ AFTER
FROM python:3.11-slim
```

### File: worker/Dockerfile

```dockerfile
# Keep as-is (already 3.11)
FROM python:3.11-slim
```

---

## MEDIUM PRIORITY FIX #2: Add Logging Configuration

### File: api/main.py (add at top)

```python
import logging
from logging.config import dictConfig

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "access": {
            "format": '%(asctime)s - %(client_addr)s - "%(request_line)s" %(status_code)s',
        },
    },
    "handlers": {
        "default": {
            "formatter": "default",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
        "access": {
            "formatter": "access",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO"},
        "uvicorn.access": {"handlers": ["access"], "level": "INFO", "propagate": False},
        "fastapi": {"handlers": ["default"], "level": "INFO"},
    },
}

dictConfig(LOGGING_CONFIG)
logger = logging.getLogger(__name__)
```

---

## MEDIUM PRIORITY FIX #3: Prometheus Metrics Singleton

### File: worker/metrics.py (improved)

```python
# ✅ IMPROVED VERSION

from prometheus_client import Counter, Gauge, Histogram, REGISTRY
import threading

_metrics_lock = threading.Lock()
_metrics = {}

def _get_or_create(metric_class, name, documentation, labelnames=None, **kwargs):
    """
    Thread-safe getter/creator for Prometheus metrics.
    Prevents duplicate registration errors.
    """
    labelnames = labelnames or []
    
    with _metrics_lock:
        # Check if already in our local cache
        if name in _metrics:
            return _metrics[name]
        
        try:
            # Try to create new metric
            metric = metric_class(name, documentation, labelnames, **kwargs)
            _metrics[name] = metric
            return metric
        except ValueError as e:
            # Already registered in Prometheus registry
            # Get it from the registry
            try:
                for collector in list(REGISTRY._collector_to_names.keys()):
                    if hasattr(collector, '_name') and collector._name == name:
                        _metrics[name] = collector
                        return collector
            except Exception:
                pass
            # If not found, raise the original error
            raise ValueError(f"Metric {name} already registered but cannot retrieve it: {e}")


# Rest of metrics definitions remain the same...
```

---

## COMPLETE REPLACEMENT: anomaly_detector.py

### File: detection/anomaly_detector.py

```python
"""
Anomaly Detection Module - Complete Implementation
Detects dwell time, crowding, and loitering anomalies
"""

import os
import time
import uuid
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
import redis
from kafka import KafkaProducer
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables with defaults
DWELL_THRESHOLD_SECONDS = int(os.getenv("DWELL_THRESHOLD_SECONDS", "300"))
CROWD_THRESHOLD = int(os.getenv("CROWD_THRESHOLD", "8"))
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

@dataclass
class AnomalyEvent:
    """Represents a detected anomaly"""
    anomaly_id: str
    anomaly_type: str  # "dwell", "crowd", "loitering"
    severity: str      # "low", "medium", "high"
    person_id: Optional[str] = None
    zone_id: Optional[str] = None
    timestamp: float = None
    description: str = ""

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class AnomalyDetector:
    """Detects anomalies in customer behavior and occupancy"""
    
    def __init__(self):
        # State for dwell: person_id -> zone_id -> enter_timestamp
        self.person_zone_enter_time: Dict[str, Dict[str, float]] = {}
        
        # State for loitering: (person_id, zone_id) -> list of entry timestamps
        self.person_zone_entries: Dict[tuple, List[float]] = {}
        
        # Deduplication cache: anomaly_key -> last_emission_timestamp
        self.last_emitted: Dict[str, float] = {}
        
        # Thresholds
        self.dwell_threshold = DWELL_THRESHOLD_SECONDS
        self.crowd_threshold = CROWD_THRESHOLD
        
        # Kafka producer
        self.kafka_producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=3
        )
        
        # Redis client
        self.redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=0,
            decode_responses=True
        )
        
        logger.info(f"AnomalyDetector initialized (dwell={DWELL_THRESHOLD_SECONDS}s, crowd={CROWD_THRESHOLD})")

    def _get_anomaly_key(self, anomaly_type: str, person_id: Optional[str], zone_id: Optional[str]) -> str:
        """Generate unique key for anomaly deduplication"""
        if person_id is None:
            return f"{anomaly_type}:{zone_id}"
        else:
            return f"{anomaly_type}:{person_id}:{zone_id}"

    def _should_emit(self, anomaly_key: str, cooldown_seconds: int = 60) -> bool:
        """Check if enough time has passed since last emission of this anomaly"""
        now = time.time()
        last_emitted = self.last_emitted.get(anomaly_key, 0)
        if now - last_emitted > cooldown_seconds:
            self.last_emitted[anomaly_key] = now
            return True
        return False

    def _emit_anomaly(self, anomaly: AnomalyEvent):
        """Emit anomaly to Kafka and store in Redis"""
        try:
            # Emit to Kafka
            self.kafka_producer.send("cv.anomalies", value=asdict(anomaly))
            self.kafka_producer.flush(timeout=10)
        except Exception as e:
            logger.error(f"Failed to send anomaly to Kafka: {e}")

        try:
            # Store in Redis
            anomaly_json = json.dumps(asdict(anomaly))
            self.redis_client.hset(f"anomaly:{anomaly.anomaly_id}", mapping={"data": anomaly_json})
            
            # Also add to sorted set for recent anomalies
            self.redis_client.zadd("anomalies:recent", {anomaly.anomaly_id: anomaly.timestamp})
            
            # Trim to last 100 anomalies
            self.redis_client.zremrangebyrank("anomalies:recent", 0, -101)
        except Exception as e:
            logger.error(f"Failed to store anomaly in Redis: {e}")

    def check_dwell(self, track_states: List[Dict], now: float) -> List[AnomalyEvent]:
        """Check for dwell anomalies (people spending too much time in zones)"""
        anomalies = []
        
        for event in track_states:
            person_id = event.get("person_id")
            zone_id = event.get("zone_id")
            event_type = event.get("event_type")
            timestamp = event.get("timestamp", now)

            if person_id is None or zone_id is None:
                continue

            if event_type == "enter":
                # Record when person entered this zone
                if person_id not in self.person_zone_enter_time:
                    self.person_zone_enter_time[person_id] = {}
                self.person_zone_enter_time[person_id][zone_id] = timestamp

            elif event_type == "exit":
                # Check dwell time
                if person_id in self.person_zone_enter_time and zone_id in self.person_zone_enter_time[person_id]:
                    enter_time = self.person_zone_enter_time[person_id][zone_id]
                    dwell_time = timestamp - enter_time
                    
                    if dwell_time >= self.dwell_threshold:
                        anomaly_key = self._get_anomaly_key("dwell", person_id, zone_id)
                        if self._should_emit(anomaly_key):
                            anomaly = AnomalyEvent(
                                anomaly_id=str(uuid.uuid4()),
                                anomaly_type="dwell",
                                severity="medium" if dwell_time < 600 else "high",
                                person_id=person_id,
                                zone_id=zone_id,
                                timestamp=timestamp,
                                description=f"Person dwelled in {zone_id} for {dwell_time:.0f}s (threshold: {self.dwell_threshold}s)"
                            )
                            anomalies.append(anomaly)
                    
                    # Clean up
                    del self.person_zone_enter_time[person_id][zone_id]
        
        return anomalies

    def check_crowd(self, detections: List[Dict], zone_id: str, now: float) -> Optional[AnomalyEvent]:
        """Check for crowding anomalies (too many people in a zone)"""
        if not detections or not zone_id:
            return None
        
        crowd_count = len(detections)
        
        if crowd_count >= self.crowd_threshold:
            anomaly_key = self._get_anomaly_key("crowd", None, zone_id)
            if self._should_emit(anomaly_key, cooldown_seconds=30):
                severity = "low" if crowd_count < self.crowd_threshold * 1.5 else (
                    "medium" if crowd_count < self.crowd_threshold * 2 else "high"
                )
                
                anomaly = AnomalyEvent(
                    anomaly_id=str(uuid.uuid4()),
                    anomaly_type="crowd",
                    severity=severity,
                    zone_id=zone_id,
                    timestamp=now,
                    description=f"Crowding detected in {zone_id}: {crowd_count} people (threshold: {self.crowd_threshold})"
                )
                return anomaly
        
        return None

    def check_loitering(self, track_history: Dict[str, List[Dict]], zone_id: str, now: float) -> Optional[AnomalyEvent]:
        """Check for loitering (repeated entries/exits in short time)"""
        if not track_history or not zone_id:
            return None
        
        loitering_threshold = 3  # 3 entries in 5 minutes = loitering
        window_seconds = 300
        
        for person_id, events in track_history.items():
            zone_events = [e for e in events if e.get("zone_id") == zone_id]
            
            # Count entries in the time window
            recent_entries = [e for e in zone_events if now - e.get("timestamp", now) < window_seconds and e.get("event_type") == "enter"]
            
            if len(recent_entries) >= loitering_threshold:
                anomaly_key = self._get_anomaly_key("loitering", person_id, zone_id)
                if self._should_emit(anomaly_key, cooldown_seconds=60):
                    anomaly = AnomalyEvent(
                        anomaly_id=str(uuid.uuid4()),
                        anomaly_type="loitering",
                        severity="low",
                        person_id=person_id,
                        zone_id=zone_id,
                        timestamp=now,
                        description=f"Loitering detected: {len(recent_entries)} entries in {zone_id} within 5 minutes"
                    )
                    return anomaly
        
        return None

    def process_frame(
        self,
        customer_events: Optional[List[Dict]] = None,
        detections: Optional[List[Dict]] = None,
        timestamp: Optional[float] = None,
        zone_id: str = "unknown",
    ) -> List[AnomalyEvent]:
        """Process frame and detect all anomalies"""
        anomalies = []
        timestamp = timestamp or time.time()
        customer_events = customer_events or []
        detections = detections or []
        
        # Check dwell time anomalies
        dwell_anomalies = self.check_dwell(customer_events, timestamp)
        anomalies.extend(dwell_anomalies)
        
        # Check crowding anomalies
        crowd_anomaly = self.check_crowd(detections, zone_id, timestamp)
        if crowd_anomaly:
            anomalies.append(crowd_anomaly)
        
        # Emit all detected anomalies
        for anomaly in anomalies:
            self._emit_anomaly(anomaly)
        
        return anomalies

    def close(self):
        """Cleanup resources"""
        try:
            self.kafka_producer.close()
            self.redis_client.close()
            logger.info("AnomalyDetector closed")
        except Exception as e:
            logger.error(f"Error closing AnomalyDetector: {e}")


# Singleton instance
_detector = None

def get_anomaly_detector() -> AnomalyDetector:
    """Get or create singleton anomaly detector"""
    global _detector
    if _detector is None:
        _detector = AnomalyDetector()
    return _detector
```

---

## MEDIUM PRIORITY FIX #4: Document Environment Variables

### File: .env.example (complete)

```bash
# ============================================================
# STORE INTELLIGENCE SYSTEM - ENVIRONMENT CONFIGURATION
# ============================================================

# ─── API Configuration ───────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8000
APP_ENV=production
LOG_LEVEL=info

# ─── Redis Configuration ─────────────────────────────────
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
# REDIS_PASSWORD=  # Optional: Set if Redis requires authentication

# ─── Kafka Configuration ─────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
KAFKA_CONSUMER_GROUP=cv-api-consumers
KAFKA_TOPIC_DETECTIONS=cv.detections
KAFKA_TOPIC_ANOMALIES=cv.anomalies

# ─── Worker Configuration ────────────────────────────────
VIDEO_SOURCE=0                    # 0 for webcam, or file path
CAMERA_ID=camera_0
MIN_CONFIDENCE=0.4
FRAME_SKIP=3

# ─── Anomaly Detection ───────────────────────────────────
DWELL_THRESHOLD_SECONDS=300
CROWD_THRESHOLD=8

# ─── Dashboard Configuration ─────────────────────────────
VITE_API_URL=http://localhost:8000
VITE_WS_URL=ws://localhost:8000

# ─── Monitoring ──────────────────────────────────────────
PROMETHEUS_SCRAPE_INTERVAL=15s
GRAFANA_PASSWORD=admin_secure_password_change_this

# ─── Deployment ──────────────────────────────────────────
DEPLOYMENT_ENV=production
```

