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
    ▼ [DetectionEvent, FootfallEvent, AnomalyEvent]
Consumer Service (Python)
    │
    ▼ [Aggregated metrics: counts, dwell times, anomaly flags]
Redis (In-memory datastore)
    │
    ▼ [Real-time counters, hashed user sessions, sorted sets for trends]
FastAPI Service
    │
    ▼ [JSON API responses: dashboard data, alerts]
Web Dashboard (React)
    │
    ▼ [Visualized metrics: footfall heatmaps, staff performance, alerts]
```

## 3. Component Breakdown

### Worker Service
- **Responsibilities**: Ingest RTSP streams from CCTV, run YOLOv8-person model for detection, track individuals via SORT algorithm, filter staff via uniform color/badge detection, emit DetectionEvents.
- **Inputs**: RTSP video stream (configurable per camera), staff uniform HSV ranges, detection confidence threshold (0.5).
- **Outputs**: DetectionEvent JSON to Kafka topic `store-events` at 1 FPS per camera.
- **Technologies**: Python 3.10, OpenCV, Ultralytics YOLOv8, SORT tracker, confluent-kafka.

### Event Schema
- **DetectionEvent**: 
  ```json
  {
    "event_id": "uuid",
    "timestamp": "ISO 8601",
    "camera_id": "string",
    "person_id": "int (track ID)",
    "bbox": [x, y, width, height],
    "confidence": "float (0-1)",
    "is_staff": "boolean",
    "store_zone": "string (from config)"
  }
  ```
- **FootfallEvent** (aggregated per minute per zone):
  ```json
  {
    "window_start": "ISO 8601",
    "window_end": "ISO 8601",
    "zone": "string",
    "unique_visitors": "int (deduplicated by person_id)",
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
    "person_ids": "list[int]",
    "duration": "float (seconds)",
    "threshold_breached": "float"
  }
  ```

### API Service (FastAPI)
- **Endpoints**:
  - `GET /api/v1/footfall?zone=&start=&end=` → Returns FootfallEvent array (target: <100ms)
  - `GET /api/v1/anomalies?type=&limit=50` → Returns AnomalyEvent array (target: <150ms)
  - `GET /api/v1/staff-performance?date=` → Returns staff zone time, customer interactions (target: <200ms)
  - `GET /api/v1/heatmap?zone=&resolution=10m` → Returns 2D density array (target: <300ms)
  - `POST /api/v1/alerts` → Create manual alert (target: <50ms)
  - `GET /health` → Liveness probe (target: <10ms)
- **Tech**: Python 3.10, FastAPI, Uvicorn, Pydantic v2, Redis-py.

### Redis Data Model
- **Keys**:
  - `store:{store_id}:zone:{zone}:footfall:minute` → Hash: `{entries, exits, unique, dwell_sum}` (TTL: 7d)
  - `store:{store_id}:tracking:active` → Set of current person_ids (TTL: 2h, renewed per detection)
  - `store:{store_id}:person:{person_id}:session` → Hash: `{first_seen, last_seen, zone_history, is_staff}` (TTL: 2h)
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
2. Worker service detects person via YOLOv8, assigns track ID, checks uniform color (not staff).
3. DetectionEvent published to Kafka with `is_staff=false`, `timestamp`, `bbox`.
4. Consumer service receives event, updates Redis:
   - Adds person_id to `tracking:active` set
   - Creates/updates `person:{person_id}:session` hash (first_seen if new)
   - If person exits zone (tracked via disappearing for >30s), calculates dwell time, increments zone footfall hash.
5. Every minute, consumer aggregates zone footfall hash into FootfallEvent, publishes to Kafka.
6. Separate anomaly consumer detects loitering (dwell > 300s in non-product zone), emits AnomalyEvent.
7. FastAPI serves dashboard requests by reading aggregated data from Redis (footfall hashes, anomaly streams).
8. Dashboard updates UI components based on data freshness.

## 5. Assumptions Made
- CCTV cameras provide 1080p@15fps RTSP streams with H.264 codec, positioned at 3m height covering entrances and key zones.
- Store layout is static during operation; zones (entrance, checkout, product aisles, staff-only) are pre-configured in worker service.
- Staff wear uniform with detectable color range (HSV: [20,100,100]-[30,255,255] for blue) or wear issued RFID badges (simulated via color detection).
- No significant occlusion from shelves; cameras cover ≥80% of floor area with <45° angle.
- Customer re-entry within 30 minutes is considered same visit (session TTL=2h).
- Store operates 10h/day; peak traffic modeled as 2 persons/second at entrances.

## 6. Scalability Path
- **1 store → 10 stores**: 
  - Partition Kafka topics by `store_id` (e.g., `store-events-{store_id}`).
  - Horizontal scale consumer service (more instances per store).
  - Redis Cluster with 3 nodes (1 per 3 stores), keys hashed by store_id.
  - FastAPI behind Nginx, scaled via Gunicorn workers (4 workers/core).
- **10 stores → 100 stores**:
  - Store-level Kafka clusters (regional brokers) with mirroring to central analytics topic.
  - Consumer service grouped by store_id using Kafka consumer groups.
  - Redis Cluster expanded to 10 nodes, using hash tags `{store_id}` for atomic operations.
  - FastAPI microservices split: footfall service, anomaly service, staff service.
  - Dashboard uses store selector to fetch data from relevant backend instance.
  - Centralized config service (Consul) for zone/uniform thresholds.

## 7. Known Edge Cases and Handling
- **Re-entry**: If person_id reappears in `tracking:active` after expiration (>2h gap), treated as new visitor. Short gaps (<30s) ignored via session renewal on detection.
- **Occlusion**: If person disappears for <15s, retain in `tracking:active` with last known position. If >15s, compute exit event. Uses Kalman filter in SORT for prediction.
- **Group Entry**: Detected as multiple person_ids with similar timestamps and adjacent bboxes. FootfallEvent counts unique IDs; anomaly triggers if group size >5 loitering.
- **Staff Filtering**: Uniform detection confidence >0.7 required. Fallback to badge detection (ARUco marker) if uniform ambiguous. Staff events tagged `is_staff=true` excluded from footfall.
- **Lighting Changes**: Worker service updates HSV thresholds hourly based on scene brightness (average V channel).
- **Camera Failure**: No DetectionEvents for 30s triggers `global:store:{store_id}:status` = `"inactive"`, dashboard shows red alert.
