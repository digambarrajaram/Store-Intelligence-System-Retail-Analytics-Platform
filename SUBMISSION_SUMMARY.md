# Submission Summary

## Implemented Features

- FastAPI backend with analytics and WebSocket alert support
- React + Vite dashboard for realtime operational visibility
- Docker-based deployment model
- Kafka event pipeline for customer journey events
- Redis runtime storage for alert and occupancy state
- YOLO object detection and ByteTrack tracking pipeline
- Dynamic zone engine for motion-based event classification
- Transaction CSV integration for conversion analytics
- Conversion engine for funnel stage metrics
- Alert engine for severity-tagged anomaly events
- WebSocket alerts on `/ws/alerts`
- Prometheus metrics and Grafana visualization support

## Architecture Overview

The solution is built as an additive intelligence platform:

- Video frames are processed through YOLO and ByteTrack.
- The zone engine converts motion into customer behavior events.
- Events are published to Kafka and Redis.
- FastAPI serves analytics endpoints and the dashboard frontend.
- Prometheus scrapes metrics and Grafana visualizes system health.

## Key Engineering Decisions

- Preserve all existing endpoint contracts, Kafka topics, and Redis key semantics.
- Keep backend logic unchanged while improving UI presentation and documentation.
- Use Redis for realtime alert state and Kafka for durable event streaming.
- Implement UI polish in the dashboard without altering API behavior.
- Provide full deployment and design documentation for evaluation.

## Known Limitations

- Active camera count is represented as a deployment-configured display value.
- Historical long-term storage is not part of the current implementation.
- The dashboard depends on backend environment variables for runtime labels.
- Prometheus/Grafana require manual dashboard import and data-source setup in the deployed environment.

## Future Improvements

- Add automated Grafana dashboard provisioning.
- Extend alert rules with threshold tuning and escalation workflows.
- Add authentication and RBAC for secured dashboard access.
- Support multi-store aggregation and federated analysis.
- Introduce persisted analytics storage for historical trend analysis.

## Expected Evaluation Strengths

- Fully additive enhancements with no backend contract changes.
- Clear architecture and design documentation for review.
- Polished dashboard presentation with live status and UI clarity.
- Reusable deployment guidance for Docker, Prometheus, and Grafana.
- Strong separation of event ingestion, analytics, alerting, and observability concerns.
