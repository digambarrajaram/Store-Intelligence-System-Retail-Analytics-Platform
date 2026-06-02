# Deployment Guide

## Prerequisites

- Docker Engine installed
- Docker Compose installed
- Access to the repository codebase
- Ports available for services (default: 8000, 3000, 9090, 3001)

## Docker Installation

1. Install Docker Desktop for Windows from https://www.docker.com/get-started.
2. Verify Docker is running:
   - `docker version`
   - `docker compose version`
3. Confirm the repository is checked out and current.

## Start Services

From the repository root:

```powershell
cd D:\store-intelligence-system
docker compose up --build -d
```

To view container status:

```powershell
docker compose ps
```

## Environment Variables

Set environment values in a `.env` file or via the Docker Compose environment section.

Recommended variables:

- `VITE_API_URL` - API base URL used by the dashboard
- `VITE_WS_URL` - WebSocket URL for live alerts
- `VITE_BUILD_VERSION` - Dashboard build version label
- `VITE_ENVIRONMENT` - Deployment environment name
- `REDIS_URL` - Redis connection string
- `KAFKA_BOOTSTRAP_SERVERS` - Kafka brokers list

Example `.env` values:

```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000
VITE_BUILD_VERSION=1.0.0
VITE_ENVIRONMENT=Production
REDIS_URL=redis://redis:6379
KAFKA_BOOTSTRAP_SERVERS=kafka:9092
```

## Prometheus Setup

Prometheus is configured by `prometheus/prometheus.yml` in the repo.

- Default scrape target: the FastAPI metrics endpoint.
- Start the Prometheus service through Docker Compose.
- Access the UI at `http://localhost:9090`.

## Grafana Setup

Grafana dashboards are provided under `grafana/dashboards/store.json`.

- Start Grafana through Docker Compose.
- Import the JSON dashboard when prompted.
- Link Grafana to Prometheus as the data source.

## Health Checks

Verify service health by checking the following endpoints:

- API availability: `http://localhost:8000/docs`
- Metrics: `http://localhost:8000/metrics`
- Dashboard load: `http://localhost:3000`
- Prometheus UI: `http://localhost:9090`
- Grafana UI: `http://localhost:3001`

Also inspect Docker logs:

```powershell
docker compose logs -f
```

## Troubleshooting

- If the dashboard does not load, confirm `VITE_API_URL` and `VITE_WS_URL` point to the running API.
- If WebSocket alerts are missing, check `docker compose logs worker` and Redis connectivity.
- If Prometheus is not scraping, verify the scrape config and target port.
- If Grafana has no data, confirm Prometheus is healthy and the data source is configured.

## Rollback Procedure

To stop the deployment safely:

```powershell
docker compose down
```

If a rollback is required:

1. Revert code changes in the repo.
2. Rebuild and restart:
   ```powershell
docker compose up --build -d
```
3. Confirm the API and dashboard return to the previous known-good state.
