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

## Why React + Vite?

- React provides a composable UI model for KPI cards, alert feeds, and charts.
- Vite offers fast startup, hot module replacement, and optimized production builds.
- The dashboard benefits from lightweight client delivery and modern TypeScript support.

Tradeoffs:
- Strength: excellent developer experience and responsive UI updates.
- Tradeoff: requires a build step and frontend tooling versus vanilla HTML.

Rejected alternatives:
- Angular: heavier framework and more complex setup for a dashboard.
- Plain server-rendered HTML: less interactive and no realtime UI feel.

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

## Why YOLO?

- YOLO provides proven object detection speed and accuracy for retail camera frames.
- It supports the target use case of detecting people and staff in real time.

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
- It integrates naturally with Prometheus and supports the project’s Grafana JSON dashboards.

Tradeoffs:
- Strength: powerful and customizable visualization.
- Tradeoff: additional deployment and configuration effort.

Rejected alternatives:
- Kibana: more suited to log analytics than metric dashboards.
- In-app charts only: wouldn’t provide the enterprise monitoring experience expected in evaluation.
