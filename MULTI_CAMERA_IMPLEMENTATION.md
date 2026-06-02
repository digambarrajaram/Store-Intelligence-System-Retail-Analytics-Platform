# Multi-Camera Implementation - Complete Changes & Deployment Guide

## Overview

This document provides a complete summary of all code changes made to support multi-camera (5x CCTV) analytics processing. The system now processes CAM 1.mp4 through CAM 5.mp4 concurrently with aggregated store-level metrics and per-camera drill-down capabilities.

---

## Summary of Changes

### 1. Docker Compose Configuration ✅

**File**: `docker-compose.yml`

**Changes**:
- Replaced single `worker` container with 5 camera-specific workers (`worker_cam_1` through `worker_cam_5`)
- Each worker has unique:
  - `CAMERA_ID` environment variable (camera_1 → camera_5)
  - `VIDEO_PATH` environment variable (CAM 1.mp4 → CAM 5.mp4)
  - Port mapping (8001 → 8005 for Prometheus metrics)
  - Healthcheck key (camera-specific Redis key)
- Maintained all service dependencies and networking

**Key Implementation**:
```yaml
worker_cam_1:
  environment:
    CAMERA_ID: camera_1
    VIDEO_PATH: /app/videos/CAM 1.mp4
  healthcheck:
    test: ["CMD", "python", "-c", "import redis; r=redis.Redis(...); exit(0 if r.get('camera_1:worker.alive') == '1' else 1)"]

# ... repeated for cameras 2-5
```

---

### 2. Worker Service Updates ✅

**File**: `worker/worker.py`

**Changes**:

#### A. Camera-Specific Heartbeat Keys
```python
# BEFORE
r.set('worker.alive', '1', ex=120)
r.set('worker:last_heartbeat', time.time())

# AFTER
r.set(f'{CAMERA_ID}:worker.alive', '1', ex=120)
r.set(f'{CAMERA_ID}:worker:last_heartbeat', time.time())
```

#### B. Kafka Partition Key (camera_id)
```python
# BEFORE
await producer.send(KAFKA_TOPIC, event)

# AFTER
await producer.send(KAFKA_TOPIC, event, key=CAMERA_ID.encode('utf-8'))
```
**Impact**: Events are now partitioned by camera_id, enabling per-camera Kafka offset tracking and replay.

#### C. ConversionEngine Initialization
```python
# BEFORE
conversion_engine = ConversionEngine(r)

# AFTER
conversion_engine = ConversionEngine(r, camera_id=CAMERA_ID)
```

---

### 3. Kafka Consumer Updates ✅

**File**: `api/kafka_consumer.py`

**Changes**: Complete rewrite to support camera-specific and store-level aggregation

#### Key Updates:
```python
# Extract camera_id from event
camera_id = event.get("camera_id", "unknown")

# Store camera-specific entries
await redis.zadd(f"camera:{camera_id}:entries", {track_id: now})

# Also add to store-wide for aggregation
await redis.zadd("store:entries", {f"{camera_id}:{track_id}": now})

# Track camera-specific active tracks
await redis.sadd(f"camera:{camera_id}:active_tracks", *list(current_tracks))

# Per-camera occupancy metrics
await redis.set(f"camera:{camera_id}:current_occupancy", occupancy)
await redis.set(f"camera:{camera_id}:peak_occupancy", max_occupancy)

# Store-wide aggregation
all_cameras_occupancy = sum(...)
await redis.set("store:peak_occupancy", all_cameras_occupancy)
```

---

### 4. API Enhancement ✅

**File**: `api/routers/analytics.py`

**Changes**: Added `camera_id` query parameter to all metrics endpoints

#### A. `/store-metrics` Endpoint
```python
@router.get("/store-metrics")
async def get_metrics(
    request: Request,
    window_minutes: int = Query(60, ge=1, le=1440),
    camera_id: str = Query(None),  # NEW PARAMETER
):
    # ... helper function to get metrics for specific camera or store-wide
    
    if camera_id == "all":
        # Return per-camera breakdown
        metrics = {}
        for cam_num in range(1, 6):
            cam_id = f"camera_{cam_num}"
            metrics[cam_id] = await get_camera_metrics(cam_id)
        metrics["store"] = await get_camera_metrics(None)
        return {"cameras": metrics}
    elif camera_id:
        # Return specific camera metrics
        return await get_camera_metrics(camera_id)
    else:
        # Return store-wide metrics
        return await get_camera_metrics(None)
```

**Usage Examples**:
```bash
# Store-wide metrics
curl http://localhost:8000/api/v1/store-metrics

# Camera 1 metrics
curl http://localhost:8000/api/v1/store-metrics?camera_id=camera_1

# Per-camera breakdown
curl http://localhost:8000/api/v1/store-metrics?camera_id=all
```

#### B. `/funnel` Endpoint
```python
@router.get("/funnel")
async def get_funnel(request: Request, camera_id: str = Query(None)):
    # Supports same ?camera_id parameter patterns
    # Returns funnel data per-camera or aggregated
```

#### C. `/occupancy/history` Endpoint
```python
@router.get("/occupancy/history")
async def get_occupancy_history(
    request: Request,
    window_minutes: int = Query(60, ge=5, le=1440),
    interval_minutes: int = Query(5, ge=1, le=60),
    camera_id: str = Query(None),  # NEW PARAMETER
):
    # Uses camera-specific or store-level keys
```

---

### 5. API Initialization ✅

**File**: `api/main.py`

**Changes**: Added camera metrics initialization in startup event

```python
@app.on_event("startup")
async def startup_event():
    # ... existing Redis connection code ...
    
    # NEW: Initialize camera-specific metrics keys
    print("Initializing multi-camera metrics...")
    for camera_num in range(1, 6):
        camera_id = f"camera_{camera_num}"
        await app.state.redis.set(f"{camera_id}:worker.alive", "0")
        await app.state.redis.set(f"{camera_id}:current_occupancy", "0")
        await app.state.redis.set(f"{camera_id}:peak_occupancy", "0")
        await app.state.redis.set(f"{camera_id}:anomaly_count", "0")
        await app.state.redis.set(f"{camera_id}:fps", "0")
    
    # Initialize store-wide metrics
    await app.state.redis.set("store:peak_occupancy", "0")
    await app.state.redis.set("store:anomaly_count", "0")
```

---

### 6. Conversion Engine Enhancement ✅

**File**: `services/conversion_engine.py`

**Changes**: Added camera_id support with dual-level tracking (per-camera + store-wide aggregation)

```python
class ConversionEngine:
    def __init__(self, redis_client: Any, session_timeout_seconds: int = 600, camera_id: str = None):
        self.redis = redis_client
        self.camera_id = camera_id or "store"
    
    def _active_session_key(self, track_id: str) -> str:
        return f'funnel:{self.camera_id}:active_session:{track_id}'
    
    def process_customer_events(self, events: List[Dict[str, Any]]) -> None:
        # Track per-camera funnel
        self.redis.sadd(f'funnel:{self.camera_id}:entered_store', session_id)
        
        # Also track store-wide
        self.redis.sadd('funnel:store:entered_store', session_id)
```

**Result**: Each camera maintains independent funnel tracking while contributing to store-wide aggregates.

---

## Redis Key Namespace Strategy

### Camera-Specific Keys
```
camera:1:entries              (Sorted Set) - Entry timestamps for camera 1
camera:1:exits                (Sorted Set) - Exit timestamps for camera 1
camera:1:dwell_times          (Hash) - Dwell time per track
camera:1:active_tracks        (Set) - Current tracks in frame
camera:1:peak_occupancy       (Int) - Peak occupancy for this camera
camera:1:current_occupancy    (Int) - Current occupancy
camera:1:anomaly_count        (Int) - Total anomalies detected
camera:1:fps                  (Float) - Current FPS
camera:1:worker.alive         (String) - Heartbeat (health check)
funnel:camera:1:entered_store (Set) - Customers who entered via this camera
funnel:camera:1:browsed_gt_2min (Set)
funnel:camera:1:reached_checkout_zone (Set)
```

### Store-Level Aggregation
```
store:entries                 (Sorted Set) - All entries (format: "camera_1:track_id")
store:exits                   (Sorted Set) - All exits
store:peak_occupancy          (Int) - Store-wide peak
store:anomaly_count           (Int) - Total anomalies across all cameras
funnel:store:entered_store    (Set) - All customers who entered any camera
funnel:store:browsed_gt_2min  (Set)
funnel:store:reached_checkout_zone (Set)
```

---

## Deployment Instructions

### Step 1: Prepare Video Files
```bash
# Create videos directory
mkdir -p videos

# Copy your CCTV files (must be MP4 format)
cp /path/to/video_1.mp4 videos/"CAM 1.mp4"
cp /path/to/video_2.mp4 videos/"CAM 2.mp4"
cp /path/to/video_3.mp4 videos/"CAM 3.mp4"
cp /path/to/video_4.mp4 videos/"CAM 4.mp4"
cp /path/to/video_5.mp4 videos/"CAM 5.mp4"

# Verify
ls -la videos/
# Output:
# CAM 1.mp4
# CAM 2.mp4
# CAM 3.mp4
# CAM 4.mp4
# CAM 5.mp4
```

### Step 2: Pre-Create Kafka Topic (Optional but Recommended)
```bash
# Start Kafka container
docker compose up kafka zookeeper -d

# Wait for Kafka to be healthy
docker exec kafka kafka-topics \
  --create \
  --topic cv.detections \
  --partitions 5 \
  --replication-factor 1 \
  --bootstrap-server localhost:9092 \
  --if-not-exists

# Verify
docker exec kafka kafka-topics \
  --describe \
  --topic cv.detections \
  --bootstrap-server localhost:9092
```

### Step 3: Build and Start All Services
```bash
# Build all images
docker compose build --no-cache

# Start all services
docker compose up -d

# Verify all containers are running
docker compose ps
```

### Step 4: Verify Health Checks
```bash
# Check API health
curl http://localhost:8000/health
# Expected output: {"status": "healthy", "services": {"redis": "ok", "kafka": "ok"}, ...}

# Check Redis connectivity
docker exec redis redis-cli ping
# Expected: PONG

# Check Kafka topics
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092
# Should show: cv.detections
```

---

## Verification Commands

### System Health
```bash
# Check all containers
docker compose ps

# Check worker logs
docker compose logs worker_cam_1
docker compose logs worker_cam_2
docker compose logs worker_cam_3
docker compose logs worker_cam_4
docker compose logs worker_cam_5

# Check API logs
docker compose logs api

# Monitor real-time
docker compose logs -f api
```

### API Endpoints Testing

#### 1. Store-Wide Metrics
```bash
curl -s http://localhost:8000/api/v1/store-metrics | jq '.'

# Expected response:
{
  "period_start": "2024-06-02T10:00:00+00:00",
  "period_end": "2024-06-02T11:00:00+00:00",
  "total_entries": 450,
  "total_exits": 380,
  "current_occupancy": 70,
  "peak_occupancy": 95,
  "avg_dwell_minutes": 12.5,
  "anomaly_count": 3,
  "camera_fps": 25.0
}
```

#### 2. Camera-Specific Metrics
```bash
# Camera 1 only
curl -s "http://localhost:8000/api/v1/store-metrics?camera_id=camera_1" | jq '.'

# Expected response:
{
  "period_start": "2024-06-02T10:00:00+00:00",
  "period_end": "2024-06-02T11:00:00+00:00",
  "camera_id": "camera_1",
  "total_entries": 90,
  "total_exits": 75,
  "current_occupancy": 15,
  "peak_occupancy": 25,
  "avg_dwell_minutes": 11.3,
  "anomaly_count": 0,
  "camera_fps": 25.0
}
```

#### 3. Per-Camera Breakdown
```bash
# All cameras with store aggregate
curl -s "http://localhost:8000/api/v1/store-metrics?camera_id=all" | jq '.'

# Expected response:
{
  "period_start": "2024-06-02T10:00:00+00:00",
  "period_end": "2024-06-02T11:00:00+00:00",
  "cameras": {
    "camera_1": {...metrics...},
    "camera_2": {...metrics...},
    "camera_3": {...metrics...},
    "camera_4": {...metrics...},
    "camera_5": {...metrics...},
    "store": {...aggregated metrics...}
  }
}
```

#### 4. Funnel Metrics
```bash
# Store-wide funnel
curl -s http://localhost:8000/api/v1/funnel | jq '.'

# Camera-specific funnel
curl -s "http://localhost:8000/api/v1/funnel?camera_id=camera_1" | jq '.'

# Per-camera funnel breakdown
curl -s "http://localhost:8000/api/v1/funnel?camera_id=all" | jq '.'
```

#### 5. Occupancy History
```bash
# Store-wide occupancy over last 60 minutes
curl -s http://localhost:8000/api/v1/occupancy/history | jq '.'

# Camera 1 occupancy
curl -s "http://localhost:8000/api/v1/occupancy/history?camera_id=camera_1" | jq '.'
```

### Redis Data Inspection
```bash
# Connect to Redis CLI
docker exec -it redis redis-cli

# Check camera 1 entries
ZCARD camera:1:entries

# Check store-wide entries
ZCARD store:entries

# Check current occupancy per camera
GET camera:1:current_occupancy
GET camera:2:current_occupancy
# ... etc

# Check funnel progression per camera
SMEMBERS funnel:camera:1:entered_store
SMEMBERS funnel:camera:1:browsed_gt_2min
SMEMBERS funnel:camera:1:reached_checkout_zone

# Check store-wide funnel
SMEMBERS funnel:store:entered_store

# Check worker heartbeats
GET camera_1:worker.alive
GET camera_2:worker.alive
# ... etc

# Monitor in real-time
MONITOR
```

### Kafka Inspection
```bash
# List topics
docker exec kafka kafka-topics --list --bootstrap-server localhost:9092

# Describe cv.detections topic
docker exec kafka kafka-topics --describe --topic cv.detections --bootstrap-server localhost:9092

# Check consumer groups
docker exec kafka kafka-consumer-groups --list --bootstrap-server localhost:9092

# Describe analytics consumer group
docker exec kafka kafka-consumer-groups --describe --group analytics-group --bootstrap-server localhost:9092

# Read messages from topic (from latest)
docker exec kafka kafka-console-consumer \
  --topic cv.detections \
  --from-beginning \
  --bootstrap-server localhost:9092 \
  --max-messages 5
```

---

## Expected Output Examples

### Worker Startup Log
```
[camera_1] Processing frame 150 at 25.0 fps
[camera_1] YOLOv8n model loaded
[camera_1] VideoProcessor initialized
[camera_1] ConversionEngine initialized for camera_1
[camera_1] AlertEngine initialized
[camera_1] Kafka producer connected on attempt 1
[camera_1] Redis connected on attempt 1
[camera_1] Initial heartbeat written to camera_1:worker.alive
[camera_1] Video opened: /app/videos/CAM 1.mp4 (1920x1080 @ 25.0fps)
```

### API Initialization Log
```
Initializing background data streaming interfaces...
Connecting to Redis cluster at redis:6379...
Initializing multi-camera metrics...
Camera metrics initialized
Kafka consumer started
Application startup sequence finalized.
Starting Kafka consumer for topic cv.detections on kafka:9092
```

### Redis Metrics Example (from Kafka Consumer Processing)
```
camera:1:entries = 450 entries
camera:1:exits = 380 exits
camera:1:current_occupancy = 70
camera:1:peak_occupancy = 95
camera:1:fps = 25.0

camera:2:entries = 420 entries
camera:2:exits = 365 exits
camera:2:current_occupancy = 55
camera:2:peak_occupancy = 85
camera:2:fps = 25.0

store:peak_occupancy = 380 (sum of all cameras)
funnel:store:entered_store = 2250 (all customers)
funnel:store:browsed_gt_2min = 1650 (73% conversion)
```

---

## Troubleshooting

### Issue 1: Workers Not Connecting to Kafka
```
ERROR: Could not connect to Kafka after 10 attempts. Exiting.
```

**Solution**:
```bash
# Check Kafka container status
docker compose ps kafka

# Check Kafka logs
docker compose logs kafka

# Verify Kafka is healthy
docker exec kafka kafka-broker-api-versions --bootstrap-server localhost:9092

# Manually start Kafka if needed
docker compose up kafka zookeeper -d --wait
```

### Issue 2: Redis Heartbeat Failing
```
[camera_1] Redis connection attempt 1 failed: Error
```

**Solution**:
```bash
# Check Redis container
docker compose ps redis

# Check Redis logs
docker compose logs redis

# Test Redis connectivity
docker exec redis redis-cli ping

# Restart Redis
docker compose restart redis
```

### Issue 3: Video File Not Found
```
WARNING: Video file not found at /app/videos/CAM 1.mp4. Running in demo mode.
```

**Solution**:
```bash
# Check videos directory
ls -la videos/

# Verify file names match exactly (case-sensitive)
# File should be: "CAM 1.mp4" (with space)

# Re-copy files if needed
cp source_video.mp4 videos/"CAM 1.mp4"
```

### Issue 4: API Not Returning Metrics
```
curl http://localhost:8000/api/v1/store-metrics
# Returns: {"total_entries": 0, "total_exits": 0, ...}
```

**Solution**:
1. Wait 30-60 seconds for workers to process initial frames
2. Check Redis consumer is running: `docker compose logs api | grep "Kafka consumer started"`
3. Check Kafka messages exist: `docker exec kafka kafka-console-consumer --topic cv.detections --from-beginning --bootstrap-server localhost:9092`
4. Verify workers are processing: `docker compose logs worker_cam_1 | grep "Published"`

---

## Performance Baseline

### Expected Throughput (Per Camera)
- **FPS**: 25 fps (video playback speed)
- **Processing FPS**: ~8 fps (YOLOv8n with ByteTrack, frame skip = 3)
- **Kafka Throughput**: ~3 messages per second per camera
- **Redis Operations**: ~15 ops per second per camera

### Multi-Camera System
- **Total Detections/sec**: ~15 per second (5 cameras × 3 events/sec)
- **Total Redis Ops/sec**: ~75 ops/sec
- **Kafka Throughput**: ~15 messages/sec
- **Memory Usage**: ~4GB (Python workers + Kafka + Redis)
- **CPU Usage**: ~60-80% on modern hardware (4+ cores)

### Recommended Hardware
- **CPU**: 4+ cores (Intel i7/Xeon or equivalent)
- **RAM**: 8GB minimum (16GB recommended)
- **Storage**: 20GB for video files + 5GB for Docker images
- **Network**: 100 Mbps (for local Docker)
- **Disk I/O**: SSD recommended for video playback

---

## Production Deployment Checklist

- [ ] All 5 CCTV video files in `/app/videos/` with correct names
- [ ] Docker Compose file updated with 5 worker containers
- [ ] Kafka topic `cv.detections` pre-created with 5 partitions
- [ ] Redis instance accessible and healthy
- [ ] All healthchecks passing: `docker compose ps`
- [ ] APIs responding to queries
- [ ] Dashboard displaying per-camera tabs
- [ ] Monitoring dashboards (Prometheus/Grafana) configured
- [ ] Logging configured with camera_id context
- [ ] Tested failover: disable one camera, verify others continue
- [ ] Tested aggregation: verify store metrics = sum of camera metrics
- [ ] Tested Kafka replay: stop consumer, restart, verify replay
- [ ] Backup strategy for Redis state defined
- [ ] Load testing completed with actual video files

---

## Next Steps: Dashboard Enhancement (Optional)

To enable per-camera tabs in the frontend dashboard:

1. Update `dashboard/src/App.tsx` to add camera selector
2. Pass `camera_id` parameter to all component hooks
3. Add per-camera metrics tabs
4. Update KPICards, OccupancyChart, FunnelChart components

See `MULTI_CAMERA_ARCHITECTURE_GUIDE.md` Phase 8 for detailed UI changes.

---

## Rollback Instructions

If you need to revert to single-camera mode:

```bash
# 1. Stop all containers
docker compose down

# 2. Reset docker-compose.yml to single worker version
git checkout docker-compose.yml

# 3. Reset worker configuration
git checkout worker/worker.py
git checkout api/kafka_consumer.py
git checkout api/routers/analytics.py

# 4. Rebuild and restart
docker compose build --no-cache
docker compose up -d
```

---

## Support & Monitoring

### Real-Time Monitoring Dashboard
Access Grafana at: `http://localhost:3001`
- Login: admin / ${GRAFANA_PASSWORD:-admin}
- Pre-configured dashboards for:
  - Per-camera metrics
  - Store-wide aggregates
  - Kafka consumer lag
  - Anomaly detection

### Prometheus Metrics
Access at: `http://localhost:9090`
- Worker metrics: http://localhost:8001/metrics (camera_1)
- API metrics: http://localhost:8000/metrics

### Health Checks
```bash
# All containers healthy
docker compose ps | grep healthy

# Quick health check
curl http://localhost:8000/health
curl http://localhost:3000/  (dashboard)
```

---

**Implementation Status**: ✅ Complete
**Date**: June 2, 2026
**Version**: 1.0.0 Multi-Camera
