# Implementation Choices

## Why FastAPI?

- FastAPI is built for asynchronous Python APIs and enables efficient request handling for realtime analytics.
- It delivers automatic OpenAPI documentation, easy middleware integration, and strong typing through Pydantic.
- FastAPI supports Prometheus instrumentation, WebSocket endpoints, and clean route organization.

Tradeoffs:
- Strength: rapid development and modern async support.
- Tradeoff: larger learning curve than Flask for teams unfamiliar with ASGI.

Rejected alternatives:
- Flask: simpler, but slower for high-concurrency realtime telemetry and less native async support.
- Django: too heavyweight for this focused analytics pipeline.

## Why React + Vite + TypeScript?

- React provides a composable UI model for KPI cards, alert feeds, and charts.
- Vite offers fast startup, hot module replacement, and optimized production builds.
- TypeScript adds type safety, reducing runtime errors in the frontend codebase.
- The dashboard benefits from lightweight client delivery and modern tooling support.

Tradeoffs:
- Strength: excellent developer experience and responsive UI updates.
- Tradeoff: requires a build step and frontend tooling versus vanilla HTML.

Rejected alternatives:
- Angular: heavier framework and more complex setup for a dashboard.
- Plain server-rendered HTML: less interactive and no realtime UI feel.

## Why Tailwind CSS?

- Tailwind provides utility-first CSS for rapid UI development without writing custom styles.
- It integrates seamlessly with Vite and keeps the dashboard styling consistent.

Tradeoffs:
- Strength: fast prototyping and consistent design system.
- Tradeoff: can lead to verbose class attributes in JSX.

Rejected alternatives:
- Bootstrap: heavier, opinionated components that are harder to customize.
- Plain CSS: more manual effort for responsive layouts.

## Why Nginx for Dashboard?

- Nginx serves the production React build with efficient static file handling and reverse proxy capabilities.
- It handles routing, caching, and can proxy API requests to the backend.

Tradeoffs:
- Strength: production-grade static file serving with low overhead.
- Tradeoff: additional service to configure and maintain.

Rejected alternatives:
- Vite dev server: not suitable for production.
- Node.js-based serving: more complex than Nginx for static files.

## Why Redis?

- Redis supplies low-latency runtime state for alerts, occupancy, and pub/sub.
- It is ideal for fast event visibility without persisting every transient event to primary storage.
- Redis pub/sub supports the existing `/ws/alerts` flow without backend contract changes.

Tradeoffs:
- Strength: fast access and realtime coordination.
- Tradeoff: not ideal for long-term historical storage, so only transient analytics are kept.

Rejected alternatives:
- SQLite/Postgres: too slow for realtime alert pub/sub.
- Redis Streams: unnecessary complexity for the existing realtime feed.

## Why Kafka?

- Kafka decouples producers and consumers, enabling independent scaling of the video worker and API analytics layers.
- It preserves event ordering and durability for conversion and alert events.
- Kafka supports rollback and replay of event streams for analytics reliability.

Tradeoffs:
- Strength: durable, scalable event bus.
- Tradeoff: more operational overhead than a simple queue.

Rejected alternatives:
- RabbitMQ: good messaging but not as strong for high-throughput event replay.
- Direct HTTP: would tightly couple components and reduce fault tolerance.

## Why YOLOv8?

- YOLOv8 provides proven object detection speed and accuracy for retail camera frames.
- It supports the target use case of detecting people and staff in real time.
- YOLOv8 offers improved accuracy and training efficiency over previous YOLO versions.

Tradeoffs:
- Strength: fast, reliable detection.
- Tradeoff: requires GPU-capable compute for high-resolution streams.

Rejected alternatives:
- OpenCV-only detection: less accurate for modern object detection.
- Custom CNN from scratch: unnecessary for the scope of this solution.

## Why ByteTrack?

- ByteTrack delivers persisted identities across frames for multi-object tracking.
- It enables event generation based on movement history rather than isolated detections.

Tradeoffs:
- Strength: better tracking fidelity for pedestrian flow.
- Tradeoff: more setup than single-frame detection.

Rejected alternatives:
- SORT: simpler but less robust for occlusions and crowded scenes.
- No tracking: would break customer journey semantics.

## Why Isolation Forest for Anomaly Detection?

- Isolation Forest is an unsupervised learning algorithm that efficiently detects anomalies by isolating outliers.
- It works well with the dwell time, crowd count, and loitering metrics collected from video analytics.
- It requires minimal parameter tuning and scales well to high-dimensional data.

Tradeoffs:
- Strength: effective for multivariate anomaly detection without labeled data.
- Tradeoff: may produce false positives in highly variable normal patterns.

Rejected alternatives:
- Statistical thresholding: too simplistic for multi-metric anomaly detection.
- Autoencoders: more complex to train and maintain for this use case.

## Why Multi-Store / Multi-Camera Architecture?

- The system supports 2 stores with 4 cameras each (8 concurrent video streams), enabling deployment across multiple retail locations.
- Each camera runs an independent worker container, allowing per-camera scaling and fault isolation.
- Store-level and camera-level metrics are aggregated in Redis for flexible querying.

Tradeoffs:
- Strength: independent scaling and fault isolation per camera.
- Tradeoff: more containers to manage compared to a single-process approach.

Rejected alternatives:
- Single worker for all cameras: would create a single point of failure and limit scalability.
- Thread-based multi-camera: Python GIL would limit concurrent processing.

## Why Zone-Based Detection?

- Zones allow defining specific areas within a camera frame (e.g., entrance, checkout, shelves) for targeted analytics.
- The zone manager service tracks entries, exits, and dwell time per zone.
- Zone configurations are stored as JSON layouts for easy customization per store and camera.

Tradeoffs:
- Strength: granular analytics per store area.
- Tradeoff: requires manual zone configuration per camera layout.

Rejected alternatives:
- Full-frame analytics: less actionable insights without zone context.
- Automated zone detection: unreliable for consistent retail layouts.

## Why Conversion Funnel Analytics?

- The conversion engine tracks customer journey stages: entered store → browsed → checkout → purchased.
- It correlates vision-based footfall data with POS transaction data to compute conversion rates.
- This provides actionable business insights on store performance.

Tradeoffs:
- Strength: bridges the gap between footfall and actual sales data.
- Tradeoff: requires accurate POS data integration for meaningful correlations.

## Why Salesperson Tracking?

- Salesperson performance is tracked by linking transactions to individual salespeople via POS data.
- The seed script initializes salesperson records, and the leaderboard ranks them by GMV.
- This enables store managers to identify top performers and optimize staffing.

Tradeoffs:
- Strength: data-driven sales performance management.
- Tradeoff: depends on accurate POS data with salesperson attribution.

## Why Staff Filtering & Re-entry Tracking?

- Staff filtering prevents employees from being counted in footfall analytics, ensuring accurate visitor metrics.
- Re-entry tracking identifies customers who leave and re-enter, preventing double-counting.
- Both features improve the accuracy of occupancy and conversion metrics.

Tradeoffs:
- Strength: more accurate analytics by filtering out non-customer movements.
- Tradeoff: requires additional tracking logic and configuration.

## Why WebSockets?

- WebSockets enable realtime alert delivery to the dashboard without polling.
- They keep the existing `/ws/alerts` endpoint intact and preserve frontend compatibility.

Tradeoffs:
- Strength: low-latency push notifications.
- Tradeoff: slightly more complex connection lifecycle than polling.

Rejected alternatives:
- Polling: adds latency and load to both client and backend.
- Server-Sent Events: less suited for bidirectional or persistent realtime state.

## Why Prometheus?

- Prometheus is a standard for scraping application metrics and collecting time-series data.
- It supports the custom counters built into the backend and worker services.

Tradeoffs:
- Strength: robust monitoring ecosystem.
- Tradeoff: requires an additional service and retention planning.

Rejected alternatives:
- Cloud monitoring only: would reduce portability and observability independence.
- Custom metric store: more work and unnecessary complexity.

## Why Grafana?

- Grafana provides flexible dashboards, alerting, and visualization for operational metrics.
- It integrates naturally with Prometheus and supports the project's Grafana JSON dashboards.

Tradeoffs:
- Strength: powerful and customizable visualization.
- Tradeoff: additional deployment and configuration effort.

Rejected alternatives:
- Kibana: more suited to log analytics than metric dashboards.
- In-app charts only: wouldn't provide the enterprise monitoring experience expected in evaluation.

## Why Docker Multi-Stage Builds?

- Two Dockerfiles are used: `Dockerfile` for worker services (YOLOv8 video processing) and `Dockerfile.api` for the FastAPI API service.
- This separation allows each service to have its own dependency set, keeping images lean.
- The `entrypoint.sh` script handles initialization (waiting for Redis, seeding data) before starting the API.

Tradeoffs:
- Strength: optimized images per service with minimal dependencies.
- Tradeoff: maintaining multiple Dockerfiles adds build complexity.

Rejected alternatives:
- Single monolithic image: would include unnecessary dependencies for each service.
- Docker Compose without separate builds: less efficient image caching.
