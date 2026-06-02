# IMPLEMENTATION CHECKLIST - Use This to Track Your Progress

## CRITICAL FIXES (Must complete before ANY deployment)

### ✅ Phase 1A: Complete Truncated Code Files (1 hour)

- [ ] **api/kafka_consumer.py** - Complete the consumer loop
  - [ ] Read: CRITICAL_FIXES_AND_IMPLEMENTATIONS.md section "CRITICAL FIX #3"
  - [ ] Copy the complete implementation
  - [ ] Test locally: `python -m py_compile api/kafka_consumer.py`
  - [ ] Verify no errors
  - [ ] Git commit: "fix: Complete kafka_consumer.py implementation"

- [ ] **detection/anomaly_detector.py** - Complete the detector
  - [ ] Read: CRITICAL_FIXES_AND_IMPLEMENTATIONS.md section "COMPLETE REPLACEMENT"
  - [ ] Copy the complete implementation
  - [ ] Test locally: `python -m py_compile detection/anomaly_detector.py`
  - [ ] Verify no errors
  - [ ] Git commit: "fix: Complete anomaly_detector.py implementation"

---

### ✅ Phase 1B: Fix Redis Connection Leaks (30 minutes)

Four files need identical fixes - Replace `Depends(get_redis)` with `request.app.state.redis`

#### api/routers/analytics.py
- [ ] Remove the `get_redis()` function
- [ ] Remove `redis: Redis = Depends(get_redis)` from function signature
- [ ] Add `request: Request` parameter
- [ ] Change `redis = request.app.state.redis` inside function
- [ ] Update all `redis.` calls to use the new variable
- [ ] Test: `python -m py_compile api/routers/analytics.py`
- [ ] Git commit: "fix: Use connection pool in analytics router"

#### api/routers/insights.py
- [ ] (Repeat same changes as above for this file)
- [ ] Test: `python -m py_compile api/routers/insights.py`
- [ ] Git commit: "fix: Use connection pool in insights router"

#### api/routers/pos.py
- [ ] (Repeat same changes as above for this file)
- [ ] Test: `python -m py_compile api/routers/pos.py`
- [ ] Git commit: "fix: Use connection pool in pos router"

#### api/routers/debug.py
- [ ] (Repeat same changes as above for this file)
- [ ] Test: `python -m py_compile api/routers/debug.py`
- [ ] Git commit: "fix: Use connection pool in debug router"

---

### ✅ Phase 1C: Fix FastAPI Startup & Background Tasks (1 hour)

**File: api/main.py**

- [ ] Import asynccontextmanager: `from contextlib import asynccontextmanager`
- [ ] Add validation functions:
  - [ ] `async def validate_redis_connection()`
  - [ ] `async def validate_kafka_bootstrap()`
  - [ ] `async def lifespan(app: FastAPI):`
- [ ] Create lifespan manager with startup logic:
  - [ ] Initialize Redis with validation
  - [ ] Pre-check Kafka
  - [ ] Initialize WebSocket manager
  - [ ] **START pub/sub listener as background task** ← KEY FIX
  - [ ] **START Kafka consumer as background task** ← KEY FIX
  - [ ] Add 5-second wait to catch startup failures
- [ ] Add shutdown logic:
  - [ ] Cancel all background tasks
  - [ ] Clean up WebSocket
  - [ ] Close Redis connection
- [ ] Change FastAPI() initialization to use `lifespan=lifespan`
- [ ] Test: `python -m py_compile api/main.py`
- [ ] Git commit: "fix: Implement proper FastAPI lifespan with background tasks"

---

### ✅ Phase 1D: Fix Kafka Configuration (15 minutes)

**File: api/main.py** - Settings class

- [ ] Find: `kafka_bootstrap_servers: str = "kafka:29092"`
- [ ] Change to: `kafka_bootstrap_servers: str = "kafka:9092"`
  - [ ] Note: 29092 is Zookeeper, 9092 is Kafka!
- [ ] Test: `python -c "from main import settings; print(settings.kafka_bootstrap_servers)"`
- [ ] Verify: Should print `kafka:9092`
- [ ] Git commit: "fix: Correct Kafka bootstrap server port (29092 → 9092)"

---

### ✅ Phase 1E: Fix Docker Environment Variables (15 minutes)

**File: docker-compose.yml** - dashboard service

- [ ] Find the dashboard service build args:
  ```yaml
  args:
    VITE_API_URL: ${VITE_API_URL:-}
    VITE_WS_URL: ${VITE_WS_URL:-}
  ```
- [ ] Change to:
  ```yaml
  args:
    VITE_API_URL: ${VITE_API_URL:-http://localhost:8000}
    VITE_WS_URL: ${VITE_WS_URL:-ws://localhost:8000}
  ```
- [ ] Find the dashboard service environment:
  ```yaml
  environment:
    - VITE_API_URL=
    - VITE_WS_URL=
  ```
- [ ] Change to:
  ```yaml
  environment:
    - VITE_API_URL=${VITE_API_URL:-http://api:8000}
    - VITE_WS_URL=${VITE_WS_URL:-ws://api:8000}
  ```
- [ ] Verify in .env file:
  - [ ] `VITE_API_URL=http://localhost:8000` (for local dev)
  - [ ] `VITE_WS_URL=ws://localhost:8000` (for local dev)
- [ ] Git commit: "fix: Set proper default values for VITE environment variables"

---

### ✅ Phase 1F: Fix WebSocket Pub/Sub Initialization (30 minutes)

**File: api/websocket.py**

- [ ] Add `pubsub_listener()` function (see CRITICAL_FIXES_AND_IMPLEMENTATIONS.md)
- [ ] Add `store_anomaly_for_catchup()` helper function
- [ ] Update `init_websocket()` to be async:
  ```python
  async def init_websocket(app: FastAPI) -> None:
      manager.redis = app.state.redis
      logger.info("[WS] WebSocket manager initialized with Redis")
  ```
- [ ] Update `cleanup_websocket()` to handle disconnections:
  ```python
  async def cleanup_websocket(app: FastAPI) -> None:
      for connection in list(manager.active_connections):
          try:
              manager.disconnect(connection)
          except Exception as e:
              logger.warning(f"[WS] Error disconnecting: {e}")
      logger.info("[WS] WebSocket cleanup complete")
  ```
- [ ] Test: `python -m py_compile api/websocket.py`
- [ ] Git commit: "fix: Implement WebSocket pub/sub listener and proper cleanup"

---

### ✅ Phase 1G: Test All Code Compiles (15 minutes)

```bash
# Navigate to project root
cd /d/store-intelligence-system

# Test all Python files compile
python -m py_compile api/main.py
python -m py_compile api/kafka_consumer.py
python -m py_compile api/websocket.py
python -m py_compile api/routers/analytics.py
python -m py_compile api/routers/insights.py
python -m py_compile api/routers/pos.py
python -m py_compile api/routers/debug.py
python -m py_compile worker/worker.py
python -m py_compile detection/anomaly_detector.py

echo "✅ All files compiled successfully!"
```

- [ ] Run all tests above
- [ ] Verify no errors
- [ ] If errors, fix and retry

---

## HIGH PRIORITY FIXES (Complete before production deployment)

### ✅ Phase 2A: Improve Error Handling in Worker (30 minutes)

**File: worker/worker.py**

- [ ] Find Kafka producer initialization loop
- [ ] After 10 retries, add:
  ```python
  else:
      print("ERROR: Could not connect to Kafka after 10 attempts. Exiting.")
      await producer.stop() if producer else None
      sys.exit(1)  # ← ADD THIS
  ```
- [ ] Add validation before using producer:
  ```python
  if producer is None:
      print("ERROR: Producer is None, cannot continue")
      sys.exit(1)
  ```
- [ ] Add similar checks for EventStore, VideoProcessor
  - [ ] Make EventStore and VideoProcessor REQUIRED (fail if not initialized)
  - [ ] Make AlertEngine OPTIONAL (warn but continue)
- [ ] Test: `python -m py_compile worker/worker.py`
- [ ] Git commit: "fix: Add exit logic for failed service initialization"

---

### ✅ Phase 2B: Fix Health Checks (30 minutes)

**File: docker-compose.yml**

- [ ] Update API healthcheck:
  ```yaml
  healthcheck:
    test: ["CMD", "curl", "-f", "--connect-timeout", "5", "--max-time", "10", "http://localhost:8000/health"]
    interval: 30s
    timeout: 15s
    retries: 5
    start_period: 60s  # ← Increased
  ```

- [ ] Update worker healthcheck:
  ```yaml
  healthcheck:
    test: ["CMD", "timeout", "5", "python", "-c", "import redis; r=redis.Redis(host='redis',port=6379,socket_connect_timeout=3); val=r.get('worker.alive'); exit(0 if val == '1' else 1)"]
    interval: 30s
    timeout: 10s
    retries: 5
    start_period: 60s  # ← Increased
  ```

- [ ] Git commit: "fix: Improve healthchecks with timeouts and better retries"

---

### ✅ Phase 2C: Use Consistent Python Version (15 minutes)

**File: Dockerfile**
- [ ] Change: `FROM python:3.10-slim` → `FROM python:3.11-slim`

**File: Dockerfile.api**
- [ ] Change: `FROM python:3.10-slim` → `FROM python:3.11-slim`

**File: worker/Dockerfile**
- [ ] Already 3.11, no change needed

- [ ] Git commit: "fix: Use consistent Python 3.11 across all Dockerfiles"

---

### ✅ Phase 2D: Document Environment Variables (20 minutes)

**File: .env.example**

- [ ] Copy the complete .env.example from CRITICAL_FIXES_AND_IMPLEMENTATIONS.md
- [ ] Or create new with all documented variables:
  - [ ] API_HOST, API_PORT, APP_ENV, LOG_LEVEL
  - [ ] REDIS_HOST, REDIS_PORT, REDIS_DB
  - [ ] KAFKA_BOOTSTRAP_SERVERS, KAFKA_CONSUMER_GROUP, KAFKA_TOPIC_DETECTIONS, KAFKA_TOPIC_ANOMALIES
  - [ ] VIDEO_SOURCE, CAMERA_ID, MIN_CONFIDENCE, FRAME_SKIP
  - [ ] DWELL_THRESHOLD_SECONDS, CROWD_THRESHOLD
  - [ ] VITE_API_URL, VITE_WS_URL
  - [ ] PROMETHEUS_SCRAPE_INTERVAL, GRAFANA_PASSWORD
  - [ ] DEPLOYMENT_ENV

- [ ] Test: `source .env.example && echo "Variables loaded"`
- [ ] Git commit: "docs: Complete environment variables documentation"

---

## TESTING PHASE (Run before deployment)

### ✅ Phase 3A: Build Docker Images Locally (30 minutes)

```bash
cd /d/store-intelligence-system

# Clean up old images
docker-compose down
docker system prune -a --volumes

# Build new images
docker-compose build --no-cache

# Expected: 4 images built successfully
docker images | grep store
```

- [ ] Run build command
- [ ] Verify: No errors
- [ ] Check image sizes are reasonable

---

### ✅ Phase 3B: Start Services Locally (5 minutes)

```bash
docker-compose up -d

# Wait for services to stabilize
sleep 60

# Check status
docker-compose ps
```

- [ ] Run command
- [ ] Verify: All services show "Up" status
- [ ] Verify: All show "healthy" in status

---

### ✅ Phase 3C: Run Verification Tests (30 minutes)

Follow the section "Verification Commands" in DEPLOYMENT_AND_VERIFICATION.md

```bash
# 1. Health checks
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/health
curl http://localhost:9090/-/healthy

# 2. Redis connectivity
docker exec -it redis redis-cli PING

# 3. Kafka connectivity
docker exec -it kafka kafka-topics --bootstrap-server kafka:9092 --list

# 4. API endpoints
curl "http://localhost:8000/api/v1/store-metrics?window_minutes=60"

# 5. Check logs for errors
docker-compose logs | grep ERROR
```

- [ ] Run all health checks
- [ ] Verify: All return success
- [ ] Verify: No ERROR logs
- [ ] Verify: All containers healthy

---

### ✅ Phase 3D: Load Test (15 minutes)

```bash
# Install loadtest if needed
npm install -g loadtest

# Run light load test
loadtest -c 10 -n 100 http://localhost:8000/api/v1/store-metrics

# Expected: Mean latency < 100ms, 0 errors
```

- [ ] Run load test
- [ ] Verify: All requests succeed
- [ ] Verify: No connection errors
- [ ] Verify: Response times reasonable

---

### ✅ Phase 3E: WebSocket Test (10 minutes)

```bash
# Install wscat if needed
npm install -g wscat

# Connect to WebSocket
wscat -c ws://localhost:8000/ws/alerts

# In another terminal, send test alert
curl -X POST http://localhost:8000/api/v1/test-alert

# Verify: WebSocket receives the alert message
```

- [ ] Connect to WebSocket
- [ ] Send test alert
- [ ] Verify: Alert received on WebSocket

---

## DEPLOYMENT PHASE

### ✅ Phase 4A: Commit All Changes to Git

```bash
git status  # Review all changes
git add -A
git commit -m "fix: Address all critical production issues"
git log --oneline -10  # Verify commits
```

- [ ] Review all changes
- [ ] Commit with descriptive message
- [ ] Verify commit appears in history

---

### ✅ Phase 4B: Push to GitHub

```bash
git push origin main

# Verify on GitHub
# github.com/digambarrajaram/store-intelligence-system
```

- [ ] Push code
- [ ] Verify on GitHub UI

---

### ✅ Phase 4C: Deploy to AWS EC2

Follow the section "AWS EC2 Deployment" in DEPLOYMENT_AND_VERIFICATION.md

```bash
# SSH into instance
ssh -i "your-key.pem" ubuntu@your-instance-ip

# Clone with latest changes
git clone https://github.com/digambarrajaram/store-intelligence-system.git
cd store-intelligence-system

# Create .env
cat > .env << 'EOF'
API_PORT=8000
REDIS_HOST=redis
REDIS_PORT=6379
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
VITE_API_URL=http://your-instance-ip:8000
VITE_WS_URL=ws://your-instance-ip:8000
EOF

# Build and start
docker-compose build --no-cache
docker-compose up -d

# Wait and verify
sleep 60
docker-compose ps
curl http://localhost:8000/health
```

- [ ] SSH into AWS instance
- [ ] Clone repository
- [ ] Create .env with actual values
- [ ] Build images
- [ ] Start services
- [ ] Verify all healthy

---

### ✅ Phase 4D: Final Production Verification

```bash
# All checks from Phase 3C, but against production URL
curl http://your-instance-ip:8000/health
curl http://your-instance-ip:8000/api/v1/store-metrics?window_minutes=60
curl http://your-instance-ip:9090/-/healthy

# Check logs
docker-compose logs api | head -50
docker-compose logs worker | head -50

# Load test against production
loadtest -c 10 -n 100 http://your-instance-ip:8000/api/v1/store-metrics
```

- [ ] Run all health checks on production URL
- [ ] Verify: No errors in logs
- [ ] Verify: Health endpoints respond
- [ ] Verify: Load test passes

---

## VALIDATION (After Deployment)

### ✅ Phase 5A: Monitor for 24 Hours

- [ ] Check error rates (should be ~0%)
- [ ] Check response times (should be <100ms)
- [ ] Check container restarts (should be 0)
- [ ] Check disk usage (should be stable)
- [ ] Check Redis connections (should be stable)

### ✅ Phase 5B: Run Smoke Tests Daily for First Week

```bash
# Check API
curl http://your-instance-ip:8000/api/v1/store-metrics

# Check Prometheus metrics
curl http://your-instance-ip:9090/api/v1/targets

# Check logs for errors
docker-compose logs | grep -i error
```

- [ ] Day 1 - All checks pass
- [ ] Day 2 - All checks pass
- [ ] Day 3 - All checks pass
- [ ] Day 4 - All checks pass
- [ ] Day 5 - All checks pass
- [ ] Day 6 - All checks pass
- [ ] Day 7 - All checks pass

---

## SUCCESS CRITERIA

System is production-ready when:

- [ ] ✅ All code compiles without errors
- [ ] ✅ All services start without errors
- [ ] ✅ All health checks pass
- [ ] ✅ Metrics appear in Prometheus
- [ ] ✅ Dashboard shows real-time data
- [ ] ✅ WebSocket delivers alerts
- [ ] ✅ Load test: 100+ req/s with <100ms latency
- [ ] ✅ Zero errors in logs for 1 hour
- [ ] ✅ No container restarts for 24 hours
- [ ] ✅ Production deployment successful
- [ ] ✅ 7-day monitoring with zero critical issues

---

## TIMELINE TRACKER

Use this to track your progress:

```
PHASE 1 (CRITICAL) - 4 hours
├─ 1A: Complete truncated code ............ [Start: __:__] [End: __:__] [ ]
├─ 1B: Fix Redis connection leaks ........ [Start: __:__] [End: __:__] [ ]
├─ 1C: Fix FastAPI startup .............. [Start: __:__] [End: __:__] [ ]
├─ 1D: Fix Kafka config ................. [Start: __:__] [End: __:__] [ ]
├─ 1E: Fix Docker env vars .............. [Start: __:__] [End: __:__] [ ]
├─ 1F: Fix WebSocket initialization ..... [Start: __:__] [End: __:__] [ ]
└─ 1G: Test all code compiles ........... [Start: __:__] [End: __:__] [ ]

PHASE 2 (HIGH PRIORITY) - 2 hours
├─ 2A: Improve worker error handling .... [Start: __:__] [End: __:__] [ ]
├─ 2B: Fix health checks ................ [Start: __:__] [End: __:__] [ ]
├─ 2C: Consistent Python version ........ [Start: __:__] [End: __:__] [ ]
└─ 2D: Document environment variables ... [Start: __:__] [End: __:__] [ ]

PHASE 3 (TESTING) - 1.5 hours
├─ 3A: Build Docker images .............. [Start: __:__] [End: __:__] [ ]
├─ 3B: Start services locally ........... [Start: __:__] [End: __:__] [ ]
├─ 3C: Run verification tests ........... [Start: __:__] [End: __:__] [ ]
├─ 3D: Load test ........................ [Start: __:__] [End: __:__] [ ]
└─ 3E: WebSocket test ................... [Start: __:__] [End: __:__] [ ]

PHASE 4 (DEPLOYMENT) - 2 hours
├─ 4A: Commit all changes ............... [Start: __:__] [End: __:__] [ ]
├─ 4B: Push to GitHub ................... [Start: __:__] [End: __:__] [ ]
├─ 4C: Deploy to AWS .................... [Start: __:__] [End: __:__] [ ]
└─ 4D: Final verification ............... [Start: __:__] [End: __:__] [ ]

TOTAL TIME: ~10 hours

PHASE 5 (VALIDATION) - Ongoing
├─ Day 1 monitoring ..................... [ ]
├─ Day 2 monitoring ..................... [ ]
├─ ...
└─ Day 7 monitoring ..................... [ ]
```

---

## ROLLBACK PROCEDURE (If Something Goes Wrong)

```bash
# If deployment fails:
git checkout HEAD~1
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

- [ ] Know where the rollback point is
- [ ] Be ready to execute within 15 minutes if needed
- [ ] Have pre-deployment backup saved

---

## NOTES FOR IMPLEMENTATION

**Key Points to Remember**:
1. Fix Redis connection leaks FIRST - this is most critical
2. Test locally before deploying
3. Don't skip any verification steps
4. Monitor closely first week
5. Have rollback ready

**Common Mistakes to Avoid**:
- ❌ Deploying without local testing
- ❌ Skipping verification commands
- ❌ Not checking logs after start
- ❌ Leaving old Docker images around
- ❌ Not updating .env file with real values

**Questions?**
- See ROOT_CAUSE_ANALYSIS_COMPLETE.md for technical details
- See CRITICAL_FIXES_AND_IMPLEMENTATIONS.md for code examples
- See DEPLOYMENT_AND_VERIFICATION.md for detailed procedures

---

**Status**: Ready to implement  
**Last Updated**: June 2, 2026  
**Estimated Completion**: June 2, 2026 + 10 hours of work

