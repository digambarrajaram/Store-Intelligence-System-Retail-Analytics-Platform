# VERIFICATION COMMANDS & DEPLOYMENT GUIDE

## Pre-Deployment Verification

### 1. Code Quality Checks

```bash
# Check for syntax errors in all Python files
cd /d/store-intelligence-system

# API files
python -m py_compile api/main.py
python -m py_compile api/kafka_consumer.py
python -m py_compile api/websocket.py
python -m py_compile api/routers/*.py

# Worker files
python -m py_compile worker/worker.py
python -m py_compile worker/metrics.py

# Services
python -m py_compile services/*.py
python -m py_compile detection/*.py

# Expected: No output = No errors
```

### 2. Docker Build Verification

```bash
# Rebuild all images (must fix code first!)
docker compose down
docker compose build --no-cache

# Expected output:
# - No errors
# - 4 images built: api, worker, dashboard, (postgres/redis/kafka from DockerHub)

# Check image sizes
docker images | grep store

# Example output:
# REPOSITORY                          TAG       SIZE
# digya285/store-intelligence-api       latest    450MB
# digya285/store-intelligence-worker    latest    2.1GB
# store-intelligence-dashboard          latest    180MB
```

### 3. Pre-Flight System Checks

```bash
# Start the system
docker compose up -d

# Wait 60 seconds for services to stabilize
sleep 60

# Verify all containers are running
docker compose ps

# Expected output: All status = "Up"
# STATUS
# Up 2 minutes (healthy)
# Up 2 minutes (healthy)
# Up 2 minutes (healthy)
# Up 2 minutes (healthy)
```

### 4. Service Health Validation

```bash
# 1. Check API health
curl -f http://localhost:8000/health
# Expected: {"status": "healthy", "services": {...}}

curl -f http://localhost:8000/api/v1/health
# Expected: Same response

# 2. Check Prometheus
curl -f http://localhost:9090/-/healthy
# Expected: Empty response, HTTP 200

# 3. Check Grafana
curl -f http://localhost:3001/api/health
# Expected: {"status":"ok"}

# 4. Check Redis connectivity
docker exec -it redis redis-cli PING
# Expected: PONG

# 5. Check Kafka connectivity
docker exec -it kafka kafka-topics --bootstrap-server kafka:9092 --list
# Expected: List of topics (cv.detections, cv.anomalies, etc.)
```

### 5. Detailed Service Logs

```bash
# API startup logs
docker logs api --tail 50

# Expected patterns:
# [STARTUP] Initializing Store Intelligence API...
# [STARTUP] ✅ Redis connected and validated
# [STARTUP] ✅ Kafka pre-check passed
# [STARTUP] ✅ WebSocket manager initialized
# [STARTUP] ✅ WebSocket pub/sub listener started
# [STARTUP] ✅ Kafka consumer started

# Worker logs
docker logs worker --tail 50

# Expected patterns:
# Redis connected on attempt 1
# Kafka producer connected on attempt 1
# YOLOv8n model loaded
# VideoProcessor initialized
# Worker started successfully

# Watch logs in real-time
docker compose logs -f api
```

### 6. Redis Validation

```bash
# Check Redis data structures
docker exec -it redis redis-cli

# Inside redis-cli:
> DBSIZE
# Expected: Integer > 0

> KEYS *
# Expected: See keys like "entries", "exits", "active_tracks", "peak_occupancy"

> GET "peak_occupancy"
# Expected: Integer (occupancy count)

> HGETALL "dwell_times"
# Expected: Hash with track_ids as keys, dwell times as values

> MONITOR
# Watch Redis commands in real-time
# Press Ctrl+C to exit
```

### 7. Kafka Message Flow

```bash
# Check Kafka topics
docker exec -it kafka kafka-topics \
  --bootstrap-server kafka:9092 \
  --list

# Expected output:
# __consumer_offsets
# cv.anomalies
# cv.detections

# Monitor messages in real-time
docker exec -it kafka kafka-console-consumer \
  --bootstrap-server kafka:9092 \
  --topic cv.detections \
  --from-beginning \
  --max-messages 5

# Expected: JSON detection events
```

### 8. API Endpoint Validation

```bash
# Test metrics endpoint
curl "http://localhost:8000/api/v1/store-metrics?window_minutes=60"
# Expected: {"period_start": "...", "total_entries": N, "total_exits": N, ...}

# Test insights endpoint
curl "http://localhost:8000/api/v1/insights/correlation?date=2024-06-02"
# Expected: {"date": "2024-06-02", "footfall": N, ...}

# Test debug endpoint
curl -X POST "http://localhost:8000/api/v1/simulate?entries=10&exits=5&anomalies=2&dwell_seconds=120"
# Expected: {"status": "simulation_complete", ...}

# Test WebSocket
wscat -c ws://localhost:8000/ws/alerts
# Expected: Connection established, receives messages
```

### 9. Prometheus Metrics Verification

```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Expected: All targets healthy
# Sample response:
# {
#   "status": "success",
#   "data": {
#     "activeTargets": [
#       {"labels": {"job": "fastapi-api"}, "state": "up"},
#       {"labels": {"job": "python-worker"}, "state": "up"},
#       {"labels": {"job": "prometheus"}, "state": "up"}
#     ]
#   }
# }

# Query metrics
curl 'http://localhost:9090/api/v1/query?query=store_current_occupancy'
# Expected: Metric values for each camera

# Check for duplicate metrics
curl 'http://localhost:9090/api/v1/query?query={__name__=~"store_entries_total|store_exits_total"}'
# Expected: Only one instance of each metric name
```

### 10. Load Test

```bash
# Install loadtest tool
npm install -g loadtest

# Run light load test (100 requests, 10 concurrent)
loadtest -c 10 -n 100 http://localhost:8000/api/v1/store-metrics

# Expected metrics:
# - Mean latency < 100ms
# - Max latency < 500ms
# - 0 errors
# - All 100 requests succeeded

# Run sustained load test (1000 requests, 50 concurrent, 30 seconds)
loadtest -c 50 -t 30 http://localhost:8000/api/v1/store-metrics

# Expected: No connection pool exhaustion, no 502 errors
```

---

## Deployment Steps

### Stage 1: Pre-Production Testing (Local)

```bash
# 1. Fix all code based on CRITICAL_FIXES_AND_IMPLEMENTATIONS.md
# 2. Run syntax checks (see section above)
# 3. Build Docker images locally
# 4. Test with docker-compose up
# 5. Run all verification commands (see section above)
# 6. Load test locally
```

### Stage 2: AWS EC2 Deployment

```bash
# 1. SSH into EC2 instance
ssh -i "your-key.pem" ubuntu@your-instance-ip

# 2. Clone repository with fixes
git clone https://github.com/digambarrajaram/store-intelligence-system.git
cd store-intelligence-system

# 3. Create .env file
cat > .env << 'EOF'
API_PORT=8000
GRAFANA_PASSWORD=secure_password_here
MIN_CONFIDENCE=0.4
FRAME_SKIP=3
CAMERA_ID=camera_brigade_road
REDIS_HOST=redis
REDIS_PORT=6379
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
VITE_API_URL=http://your-instance-ip:8000
VITE_WS_URL=ws://your-instance-ip:8000
LOG_LEVEL=info
EOF

# 4. Login to Docker Hub (for pulling images)
docker login

# 5. Pull/Build images
docker compose build --no-cache

# 6. Start services
docker compose up -d

# 7. Verify services
docker compose ps
docker compose logs -f api

# 8. Check health endpoints
curl http://localhost:8000/health
```

### Stage 3: Production Hardening

```bash
# 1. Enable Redis persistence
docker exec -it redis redis-cli CONFIG SET SAVE "900 1 300 10 60 10000"
docker exec -it redis redis-cli BGSAVE

# 2. Set Redis password
docker exec -it redis redis-cli CONFIG SET requirepass your_secure_password_123

# 3. Enable Kafka replication (multi-broker setup)
# Edit docker-compose.yml to add more kafka brokers with proper replication factor

# 4. Enable TLS for inter-service communication
# Create certificates and update docker-compose.yml volumes

# 5. Set resource limits in docker-compose.yml
# Add deploy: resources: limits: cpus, memory

# 6. Enable backup strategy
# Add volume backup script or use AWS EBS snapshots
```

### Stage 4: Monitoring & Alerting

```bash
# 1. Configure Grafana dashboards
# Access: http://localhost:3001
# Login: admin / ${GRAFANA_PASSWORD}
# Import dashboard JSON from grafana/dashboards/store.json

# 2. Create Prometheus alerting rules
cat > prometheus/alert_rules.yml << 'EOF'
groups:
  - name: store_alerts
    interval: 30s
    rules:
      - alert: HighOccupancy
        expr: store_current_occupancy > 50
        for: 5m
        annotations:
          summary: "High store occupancy detected"
      
      - alert: APIDown
        expr: up{job="fastapi-api"} == 0
        for: 1m
        annotations:
          summary: "API service is down"
      
      - alert: WorkerDown
        expr: up{job="python-worker"} == 0
        for: 1m
        annotations:
          summary: "Worker service is down"
      
      - alert: RedisConnectionErrors
        expr: rate(redis_connection_errors_total[5m]) > 0
        for: 2m
        annotations:
          summary: "Redis connection errors detected"
EOF

# 3. Configure alerting in prometheus.yml
cat >> prometheus/prometheus.yml << 'EOF'
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093
EOF

# 4. Start Alertmanager (optional)
docker run -d -p 9093:9093 --name alertmanager prom/alertmanager:latest
```

---

## Troubleshooting

### Issue: "Redis connection error - max connections reached"

**Symptom**: API returns 502 after ~100 requests

**Cause**: Connection leaks in routers (Fixed in update)

**Solution**:
```bash
# Verify fix is applied
grep -n "app.state.redis" api/routers/analytics.py
# Should return: app.state.redis (not creating new connections)

# Rebuild and restart
docker compose down
docker compose build --no-cache
docker compose up -d
```

### Issue: "WebSocket clients never receive alerts"

**Symptom**: Test alert sent but dashboard shows no notifications

**Cause**: Pub/sub listener not started (Fixed in update)

**Solution**:
```bash
# Check logs
docker logs api | grep "WebSocket pub/sub listener"
# Should see: "✅ WebSocket pub/sub listener started"

# Test alert manually
curl -X POST http://localhost:8000/api/v1/test-alert
# Check WebSocket connection receives message

# If still not working, check Redis pub/sub
docker exec -it redis redis-cli
> SUBSCRIBE anomaly_alerts
# Try publishing in another terminal:
> PUBLISH anomaly_alerts '{"test": "data"}'
```

### Issue: "Kafka consumer never started"

**Symptom**: Metrics always show 0 entries/exits

**Cause**: Startup validation failed (Fixed in update)

**Solution**:
```bash
# Check logs
docker logs api | grep "Kafka consumer"
# Look for: "✅ Kafka consumer started"

# If you see error, check Kafka connectivity
docker exec -it kafka kafka-topics --bootstrap-server kafka:9092 --list

# Verify Kafka port is correct (should be 9092, not 29092)
grep "kafka_bootstrap_servers" api/main.py

# Verify worker is publishing to Kafka
docker logs worker | grep "Kafka publish"
```

### Issue: "Healthchecks failing, containers restarting"

**Symptom**: Containers marked "unhealthy", continuous restarts

**Cause**: Healthcheck trying to access down service (Fixed in update)

**Solution**:
```bash
# Check healthcheck status
docker ps --format "{{.Names}}\t{{.Status}}"

# View healthcheck history
docker inspect api | grep -A 20 "Health"

# If Redis is slow, add timeout to health endpoint
curl --connect-timeout 5 --max-time 10 http://localhost:8000/health

# Increase start_period in docker-compose.yml (give more time for startup)
# Change from: start_period: 40s
# To:          start_period: 90s
```

### Issue: "Metrics not showing in Prometheus"

**Symptom**: Query returns "no data" in Prometheus UI

**Cause**: Duplicate metric registration or scrape timeout

**Solution**:
```bash
# Check metrics endpoint directly
curl http://localhost:8000/metrics | head -20
# Should see: # HELP store_entries_total ...

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq .

# Increase scrape timeout
# In prometheus.yml:
# scrape_interval: 15s
# scrape_timeout: 10s  # <- Change to 30s if slow
```

---

## Rollback Plan

If deployment goes wrong:

```bash
# 1. Stop all services
docker compose down

# 2. Restore from previous working state
git checkout HEAD~1  # Go back one commit

# 3. Rebuild and restart
docker compose build --no-cache
docker compose up -d

# 4. Verify
docker compose ps
curl http://localhost:8000/health
```

---

## Performance Tuning (After Successful Deployment)

### 1. Redis Connection Pool

```python
# In api/main.py, increase pool size
app.state.redis = aioredis.from_url(
    f"redis://{redis_host}:{redis_port}",
    encoding="utf-8",
    decode_responses=True,
    connection_pool_kwargs={
        "max_connections": 100,  # Increase if needed
        "retry_on_timeout": True
    }
)
```

### 2. Kafka Batch Processing

```python
# In worker/worker.py
producer = AIOKafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8'),
    batch_size=16384,  # Increase batching
    linger_ms=100      # Wait for batch to fill
)
```

### 3. Prometheus Retention

```yaml
# In docker-compose.yml, Prometheus service
command:
  - '--config.file=/etc/prometheus/prometheus.yml'
  - '--storage.tsdb.path=/prometheus'
  - '--storage.tsdb.retention.time=30d'  # Keep 30 days instead of default 15d
  - '--storage.tsdb.retention.size=50GB'  # Or use size limit
```

### 4. Redis Memory Management

```bash
# Monitor Redis memory
docker exec -it redis redis-cli INFO memory

# Set maxmemory policy (evict old data when full)
docker exec -it redis redis-cli CONFIG SET maxmemory-policy "allkeys-lru"
docker exec -it redis redis-cli CONFIG SET maxmemory 2gb
```

---

## Maintenance Tasks

### Daily

- Monitor dashboard for anomalies
- Check error rates in logs
- Verify all services healthy

### Weekly

```bash
# Check disk usage
docker system df

# Clean up unused Docker resources
docker system prune -a

# Review Prometheus retention
du -sh /var/lib/docker/volumes/prometheus_data/_data
```

### Monthly

```bash
# Backup Redis
docker exec redis redis-cli BGSAVE
docker cp redis:/data/dump.rdb ./backups/redis-$(date +%Y%m%d).rdb

# Backup Grafana dashboards
docker exec grafana grafana-cli admin export-dashboard

# Review and update dependencies
pip list --outdated
```

### Quarterly

- Security patch updates
- Python version upgrades
- Kafka/Redis version upgrades
- Capacity planning review

