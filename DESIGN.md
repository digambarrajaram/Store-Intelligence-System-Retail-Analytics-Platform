# Store Intelligence System Design

## 1. Problem Statement
Retail stores lack real-time insights into customer behavior, staff performance, and operational efficiency. Current manual counting and observational methods are inaccurate, labor-intensive, and unable to detect subtle patterns like dwell time, product interaction, or staff-customer engagement. This system automates footfall analytics, anomaly detection, and worker performance monitoring to enable data-driven decisions for staffing, layout optimization, and loss prevention.

## 2. System Architecture Overview
```
CCTV Cameras 
    │
    ▼ [Raw video streams (H.264)]
Worker Service (Python/OpenCV)
    │
    ▼ [DetectionEvent: person bounding boxes, timestamps, camera_id]
Apache Kafka (Topic: store-events)
    │
    ▼ [DetectionEvent]
API Service (Python) 
    │
    ▼ [Consumes Kafka]
    │
    ▼ [Writes aggregates to Redis]
Redis (In-memory datastore)
    │
    ▼ [Real-time counters, hashed user sessions, sorted sets for trends]
API Service (Python) 
    │
    ▼ [Reads from Redis]
    │
    ▼ [Serves JSON API]
Web Dashboard (React)
    │
    ▼ [Visualized metrics: footfall heatmaps, staff performance, alerts]
```

## 3. Component Breakdown

### Worker Service
- **Responsibilities**: Ingest RTSP streams from CCTV, run YOLOv8-person model for detection, track individuals via ByteTrack algorithm, filter staff via behavioral heuristics (dwell time > 30min, zone oscillation), emit DetectionEvents.
- **Inputs**: RTSP video stream (configurable per camera), detection confidence threshold (MIN_CONFIDENCE, defaults to 0.4).
- **Outputs**: DetectionEvent JSON to Kafka topic `store-events` at a rate configurable via FRAME_SKIP env var (processes 1 frame per FRAME_SKIP+1 frames).
- **Technologies**: Python 3.11, OpenCV, Ultralytics YOLOv8, ByteTrack tracker, aiokafka.

### Event Schema
- **DetectionEvent**: 
  ```json
  {
    "event_id": "uuid",
    "timestamp": "ISO 8601",
    "camera_id": "string",
    "track_id": "int (track ID)",
    "bbox": [x, y, width, height],
    "confidence": "float (0-1)"
  }
  ```
- **FootfallEvent** (aggregated per minute per zone):
  ```json
  {
    "window_start": "ISO 8601",
    "window_end": "ISO 8601",
    "zone": "string",
    "unique_visitors": "int (deduplicated by track_id)",
    "total_entries": "int",
    "total_exits": "int",
    "avg_dwell_time": "float (seconds)"
  }
  ```
- **AnomalyEvent**:
  ```json
  {
    "event_id": "uuid",
    "timestamp": "ISO 8601",
    "type": "enum (LOITERING, LINE_CROSSING, GROUP_ENTRY, STAFF_ABSENCE)",
    "zone": "string",
    "track_ids": "list[int]",
    "duration": "float (seconds)",
    "threshold_breached": "float"
  }
  ```

### API Service (FastAPI)
- **Endpoints**:
  - `GET /api/v1/metrics?zone=&start=&end=` → Returns FootfallEvent array (target: <100ms)
  - `GET /api/v1/anomalies?type=&limit=50` → Returns AnomalyEvent array (target: <150ms)
  - `GET /api/v1/staff-performance?date=` → Returns staff zone time, customer interactions (target: <200ms)
  - `GET /api/v1/heatmap?zone=&resolution=10m` → Returns 2D density array (target: <300ms)
  - `POST /api/v1/alerts` → Create manual alert (target: <50ms)
  - `GET /health` → Liveness probe (target: <10ms)
- **Tech**: Python 3.11, FastAPI, Uvicorn, Pydantic v2, Redis-py.

### Redis Data Model
- **Keys**:
  - `store:{store_id}:zone:{zone}:footfall:minute` → Hash: `{entries, exits, unique, dwell_sum}` (TTL: 7d)
  - `store:{store_id}:tracking:active` → Set of current track_ids (TTL: 2h, renewed per detection)
  - `store:{store_id}:person:{track_id}:session` → Hash: `{first_seen, last_seen, zone_history}` (TTL: 2h)
  - `store:{store_id}:anomalies:stream` → Sorted Set (score: timestamp, value: AnomalyEvent JSON) (TTL: 30d)
  - `store:{store_id}:staff:{staff_id}:metrics` → Hash: `{zone_seconds, interactions, breaks}` (TTL: 1d)
  - `global:store:{store_id}:status` → String: `"active"`/`"inactive"` (TTL: 5m, updated by worker heartbeat)
- **TTL Strategy**: Short-lived tracking data (2h), aggregated metrics (7d), anomalies (30d), staff metrics (1d).

### Dashboard (React)
- **Components**:
  - Real-time footfall counter (updated every 5s via WebSocket)
  - Zone-wise heatmap (canvas WebGL, updated every 30s)
  - Staff performance table (updated every 15s)
  - Anomaly alert panel (real-time via Server-Sent Events)
  - Historical trends (date range picker, updated on change)
- **Data Sources**: 
  - WebSocket connection to FastAPI `/ws/footfall` for live counts
  - REST API endpoints for historical data
  - SSE stream for anomalies (`/api/v1/anomalies/stream`)
- **Update Frequency**: 
  - Live counters: 5s
  - Heatmaps: 30s (expensive rendering)
  - Staff tables: 15s
  - Alerts: real-time

## 4. Data Flow: Customer Entry
1. Customer enters store zone covered by CCTV camera.
2. Worker service detects person via YOLOv8, assigns track ID.
3. DetectionEvent published to Kafka with `timestamp`, `bbox`, `track_id`, and `confidence`.
4. API service consumes DetectionEvent from Kafka, updates Redis:
   - Adds track_id to `tracking:active` set
   - Creates/updates `person:{track_id}:session` hash (first_seen if new)
   - If person exits zone (tracked via disappearing for >30s), calculates dwell time, increments zone footfall hash.
   - Detects anomalies based on dwell time, crowd size, loitering, etc., and emits AnomalyEvent to Redis anomalies stream.
5. Every minute, API service aggregates zone footfall hash into FootfallEvent, stores in Redis.
6. FastAPI serves dashboard requests by reading aggregated data from Redis (footfall hashes, anomaly streams).
7. Dashboard updates UI components based on data freshness.

## 5. Assumptions Made
- CCTV cameras provide 1080p@15fps RTSP streams with H.264 codec, positioned at 3m height covering entrances and key zones.
- Store layout is static during operation; zones (entrance, checkout, product aisles, staff-only) are pre-configured in worker service.
- Staff are identified by behavioral heuristics: dwell time > 30 minutes in a zone or oscillating between zones (indicating breaks).
- No significant occlusion from shelves; cameras cover ≥80% of floor area with <45° angle.
- Customer re-entry within 30 minutes is considered same visit (session TTL=2h).
- Store operates 10h/day; peak traffic modeled as 2 persons/second at entrances.

## 6. Scalability Path
- **1 store → 10 stores**: 
  - Partition Kafka topics by `store_id` (e.g., `store-events-{store_id}`).
  - Horizontal scale API service (more instances per store).
  - Redis Cluster with 3 nodes (1 per 3 stores), keys hashed by store_id.
  - FastAPI behind Nginx, scaled via Gunicorn workers (4 workers/core).
- **10 stores → 100 stores**:
  - Store-level Kafka clusters (regional brokers) with mirroring to central analytics topic.
  - API service grouped by store_id using Kafka consumer groups.
  - Redis Cluster expanded to 10 nodes, using hash tags `{store_id}` for atomic operations.
  - FastAPI microservices split: footfall service, anomaly service, staff service.
  - Dashboard uses store selector to fetch data from relevant backend instance.
  - Centralized config service (Consul) for zone/uniform thresholds.

## 7. Known Edge Cases and Handling
- **Re-entry**: If track_id reappears in `tracking:active` after expiration (>2h gap), treated as new visitor. Short gaps (<30s) ignored via session renewal on detection.
- **Occlusion**: If person disappears for <15s, retain in `tracking:active` with last known position. If >15s, compute exit event. Uses Kalman filter in ByteTrack for prediction.
- **Group Entry**: Detected as multiple track_ids with similar timestamps and adjacent bboxes. FootfallEvent counts unique track_ids; anomaly triggers if group size >5 loitering.
- **Staff Filtering**: Staff identified via behavioral heuristics (dwell time > 30min, zone oscillation). Staff events are excluded from footfall.
- **Lighting Changes**: Worker service updates detection confidence threshold hourly based on scene brightness (average V channel).
- **Camera Failure**: No DetectionEvents for 30s triggers `global:store:{store_id}:status` = `"inactive"`, dashboard shows red alert.