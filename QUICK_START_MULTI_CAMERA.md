# QUICK START - Multi-Camera Deployment Guide

## 🚀 5-Minute Setup

### Step 1: Prepare Videos
```bash
cd /path/to/store-intelligence-system

# Create videos directory
mkdir -p videos

# Copy your 5 CCTV files
cp /your/video/path/video1.mp4 videos/"CAM 1.mp4"
cp /your/video/path/video2.mp4 videos/"CAM 2.mp4"
cp /your/video/path/video3.mp4 videos/"CAM 3.mp4"
cp /your/video/path/video4.mp4 videos/"CAM 4.mp4"
cp /your/video/path/video5.mp4 videos/"CAM 5.mp4"

# Verify
ls -lh videos/
# Should show 5 files with exact names: "CAM 1.mp4" through "CAM 5.mp4"
```

### Step 2: Deploy
```bash
# Build all images (first time only, ~5 minutes)
docker compose build --no-cache

# Start all services
docker compose up -d

# Wait 30 seconds for startup
sleep 30

# Verify all containers running and healthy
docker compose ps
# All should show "healthy" status
```

### Step 3: Verify
```bash
# Test API
curl http://localhost:8000/health
# Expected: {"status": "healthy", ...}

# Get store-wide metrics
curl http://localhost:8000/api/v1/store-metrics | jq '.'

# Get camera 1 metrics
curl http://localhost:8000/api/v1/store-metrics?camera_id=camera_1 | jq '.'

# Get per-camera breakdown
curl http://localhost:8000/api/v1/store-metrics?camera_id=all | jq '.'
```

✅ **Done!** System is processing all 5 cameras.

---

## 📊 API Endpoints

### Store-Wide Metrics
```bash
curl http://localhost:8000/api/v1/store-metrics
```

### Camera-Specific Metrics
```bash
# Camera 1
curl http://localhost:8000/api/v1/store-metrics?camera_id=camera_1

# Camera 2-5
curl http://localhost:8000/api/v1/store-metrics?camera_id=camera_2
```

### Per-Camera Breakdown
```bash
curl http://localhost:8000/api/v1/store-metrics?camera_id=all
```

### Funnel Metrics
```bash
# Store-wide
curl http://localhost:8000/api/v1/funnel

# Camera 1
curl http://localhost:8000/api/v1/funnel?camera_id=camera_1

# All cameras
curl http://localhost:8000/api/v1/funnel?camera_id=all
```

### Occupancy History
```bash
# Store-wide occupancy over 60 minutes
curl http://localhost:8000/api/v1/occupancy/history

# Camera 1 occupancy
curl http://localhost:8000/api/v1/occupancy/history?camera_id=camera_1
```

---

## 🔍 Monitoring

### Dashboard
- **URL**: http://localhost:3000
- **Status**: Live per-camera and store metrics

### Prometheus Metrics
- **URL**: http://localhost:9090
- **Metrics**: http://localhost:8000/metrics (API)
- **Worker Metrics**: http://localhost:8001/metrics (camera_1)

### Grafana Dashboards
- **URL**: http://localhost:3001
- **Login**: admin / admin
- **Dashboards**: Pre-configured (if provisioning files added)

### Logs
```bash
# Watch all logs
docker compose logs -f

# Watch specific camera
docker compose logs -f worker_cam_1

# Watch API
docker compose logs -f api
```

---

## 🐛 Troubleshooting

### No metrics appearing?
```bash
# Wait 60 seconds for video processing to start
sleep 60

# Check worker status
docker compose logs worker_cam_1 | grep -i "frames\|processing\|published"

# Check if videos exist
ls -la videos/

# Check Redis population
docker exec redis redis-cli INFO stats
```

### Video file not found?
```bash
# Files must be in videos/ directory
# Names must be EXACT: "CAM 1.mp4" (with space, not "CAM_1.mp4")

# Verify
ls videos/
# Should show: CAM 1.mp4, CAM 2.mp4, etc.
```

### API not responding?
```bash
# Check if API container is running
docker compose ps api

# Check API logs
docker compose logs api | tail -50

# Restart API
docker compose restart api
```

### Container keeps restarting?
```bash
# Check logs for errors
docker compose logs worker_cam_1

# Common issues:
# 1. Video files missing: ls videos/
# 2. Kafka not ready: docker compose ps kafka
# 3. Redis not ready: docker compose ps redis

# Restart all services
docker compose down
docker compose up -d
```

---

## 📈 Expected Output

### Metrics Response Example
```json
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

### Per-Camera Example
```json
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

### Funnel Example
```json
[
  {"step": "Entered Store", "value": 450},
  {"step": "Browsed > 2 min", "value": 330},
  {"step": "Reached Checkout", "value": 180},
  {"step": "Converted", "value": 86}
]
```

---

## ⚙️ Configuration

### Environment Variables (in docker-compose.yml)
```yaml
# Per worker:
CAMERA_ID: camera_1              # camera_1 to camera_5
VIDEO_PATH: /app/videos/CAM 1.mp4
MIN_CONFIDENCE: 0.4             # YOLO confidence threshold
FRAME_SKIP: 3                   # Process every 4th frame
KAFKA_BOOTSTRAP_SERVERS: kafka:9092
REDIS_HOST: redis
```

### Changing Configuration
```yaml
# Edit docker-compose.yml
worker_cam_1:
  environment:
    MIN_CONFIDENCE: 0.5  # Lower = more detections, slower
    FRAME_SKIP: 1        # Higher = faster, fewer detections
```

Then: `docker compose up -d`

---

## 🧹 Cleanup

### Stop All Services
```bash
docker compose down
```

### Stop and Remove All Volumes (WARNING: Loses data)
```bash
docker compose down -v
```

### Prune Unused Docker Resources
```bash
docker system prune -a
```

---

## 📚 Detailed Documentation

For comprehensive documentation, see:
- **Architecture**: `MULTI_CAMERA_ARCHITECTURE_GUIDE.md`
- **Implementation**: `MULTI_CAMERA_IMPLEMENTATION.md`
- **Full Summary**: `MULTI_CAMERA_EXECUTION_SUMMARY.md`

---

## ✅ Success Checklist

- [ ] All 5 videos copied to `videos/` directory
- [ ] `docker compose build --no-cache` completed successfully
- [ ] `docker compose up -d` started all containers
- [ ] `docker compose ps` shows all containers healthy
- [ ] `curl http://localhost:8000/health` returns healthy status
- [ ] `/api/v1/store-metrics` returns metrics
- [ ] `/api/v1/store-metrics?camera_id=all` shows per-camera breakdown
- [ ] Dashboard accessible at http://localhost:3000
- [ ] Metrics increase as video plays

---

## 🎯 Next Steps

1. **Immediate**: Deploy to production using above steps
2. **Optional**: Update dashboard UI with camera selector (documented in full guide)
3. **Monitoring**: Configure Grafana dashboards and alerts
4. **Testing**: Verify metrics accuracy with known customer counts

---

**Status**: ✅ Ready for deployment  
**Version**: 1.0.0 Multi-Camera  
**Questions?**: Check MULTI_CAMERA_IMPLEMENTATION.md troubleshooting section
