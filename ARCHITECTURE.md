# ARCHITECTURE.md — CV Pipeline

> Trade-off decisions, system design rationale, and known constraints.

---

## System Overview

```
.mp4 ──► YOLOv8 Worker ──► Kafka (cv.detections) ──► FastAPI Consumer
                    │                                        │
                    └──► Kafka (cv.anomalies) ──────────────┤
                                                             │
                                               Redis (counters + pub/sub)
                                                             │
                                                   WebSocket Fan-out
                                                             │
                                                  React Dashboard
```

---

## Trade-off Decisions

### 1. Kafka over RabbitMQ / SQS

**Chose**: Confluent Kafka (local) + Upstash Kafka (prod free tier)

| Factor | Kafka | RabbitMQ |
|---|---|---|
| Replay / rewind | ✅ Yes (log retention) | ❌ No |
| Throughput | ✅ High (partitioned) | Moderate |
| Free-tier cloud | ✅ Upstash 10 GB/mo | ❌ Costly |
| Complexity | Higher | Lower |

**Decision**: Kafka's log retention lets us replay detections for model fine-tuning later (Day 4+ scope). The operational complexity is acceptable given Confluent's Docker images and Upstash's managed free tier.

---

### 2. Redis for State, Not Postgres

**Chose**: Redis (counters, sliding windows, pub/sub)

**Rationale**: Detection stats are write-heavy and time-windowed — INCR/ZSET operations at <1 ms latency beat Postgres INSERT + aggregation queries. Pub/Sub enables zero-latency WebSocket fan-out without polling.

**Trade-off**: Redis is not durable by default for ephemeral stats. We use `appendonly yes` + `appendfsync everysec` for acceptable durability. No joins needed for the Day 2 dashboard.

**Future**: Add TimescaleDB for long-term analytics if retention > 24 h is required.

---

### 3. YOLOv8n (nano) as Default

**Chose**: `yolov8n.pt` (3.2 MB, ~80 FPS on CPU)

**Trade-off**: mAP50 is ~37 vs ~50 for `yolov8m`. Acceptable for demo + free-tier deploy where GPU is not guaranteed.

**Swap path**: `YOLO_MODEL=yolov8m.pt` env var — no code change required.

---

### 4. FastAPI over Django / Flask

**Chose**: FastAPI + uvicorn

**Rationale**:
- Native `async/await` — critical for Kafka consumer + WebSocket concurrency
- Auto-generated OpenAPI docs (`/docs`) — no extra work
- Pydantic v2 for event validation at schema boundaries
- Prometheus instrumentation in 2 lines

---

### 5. Vercel (Dashboard) + Railway (API) Split Deploy

**Chose**: Split frontend/backend deploy

| Service | Platform | Cost |
|---|---|---|
| React Dashboard | Vercel | Free |
| FastAPI | Railway | Free ($5 credit/mo) |
| Redis | Upstash | Free (10k cmd/day) |
| Kafka | Upstash | Free (10 GB/mo) |

**Trade-off**: Cross-origin WebSocket requires CORS + WSS configuration. Solved via `VITE_WS_URL` env var and FastAPI CORS middleware.

**Why not Railway for everything**: Vercel's CDN gives sub-50 ms static asset delivery globally; Railway is better for long-running Python processes.

---

### 6. Anomaly Rules (Dwell + Crowd) — No ML

**Chose**: Rule-based anomaly detection (threshold on count + dwell time)

**Rationale**: ML-based anomaly detection (e.g., autoencoder on trajectory embeddings) requires training data we don't have at Day 1. Rule-based is interpretable, tunable via env vars, and zero latency.

**Future**: Replace `AnomalyDetector` with an LSTM trajectory model or Isolation Forest on dwell features using the Kafka replay log.

---

### 7. ByteTrack for Multi-Object Tracking

**Chose**: YOLOv8's built-in `model.track(persist=True)` which uses ByteTrack

**Rationale**: Dwell-time anomalies require stable `track_id` across frames. ByteTrack has near-zero overhead and is bundled with Ultralytics — no extra dependency.

**Trade-off**: Track IDs reset on worker restart. For production, use a persistent tracker (DeepSORT + ReID) with Redis-backed ID continuity.

---

## Scaling Path (Post-Demo)

```
Single worker → Worker pool (Kafka consumer group, 1 partition = 1 worker)
Single broker → Kafka cluster (3 brokers, RF=2)
Redis standalone → Redis Cluster or Upstash Multi-Region
FastAPI 1 worker → FastAPI 4 workers behind nginx (or Fly.io autoscale)
```

---

## Known Constraints

- **GPU**: Worker `docker-compose.yml` has NVIDIA runtime block; comment out on non-GPU hosts.
- **Video loop**: `VIDEO_LOOP=true` loops the .mp4 for demo purposes — disable in production.
- **Upstash Kafka free tier**: 10 GB/month data transfer, 100 MB/day. Sufficient for demo; ~1 KB/detection × 30 fps ÷ 3 frame-skip = ~3.6 MB/hour.
- **Upstash Redis free tier**: 10,000 commands/day. Use `FRAME_SKIP=5` or higher to stay within limits.
