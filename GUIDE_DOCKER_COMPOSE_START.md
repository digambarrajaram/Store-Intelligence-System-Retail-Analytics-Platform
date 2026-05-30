# Docker Compose Start Guide

This guide provides instructions for starting and managing the CV Pipeline Docker Compose stack.

## Prerequisites

- Docker Engine (version 20.10+)
- Docker Compose (v2.x, included with Docker Desktop)
- For GPU support: NVIDIA drivers and [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)

## Starting the Stack

### Basic Startup

To start all services in detached mode (in the background):

```bash
docker compose up -d
```

To start services and view logs in real-time (attached mode):

```bash
docker compose up
```

### Starting Specific Services

To start only specific services (e.g., just the API and dependencies):

```bash
docker compose up -d api kafka redis
```

### Rebuilding Images

If you've changed Dockerfiles or application code, rebuild images:

```bash
docker compose up -d --build
```

To force rebuild without using cache:

```bash
docker compose up -d --build --no-cache
```

## Managing the Stack

### Viewing Service Status

```bash
docker compose ps
```

### Viewing Logs

To view logs for all services:

```bash
docker compose logs -f
```

To view logs for a specific service (e.g., worker):

```bash
docker compose logs -f worker
```

### Stopping the Stack

To stop all services but preserve containers:

```bash
docker compose stop
```

To stop and remove containers, networks, and volumes:

```bash
docker compose down
```

To remove volumes as well (e.g., to reset persistent data like Kafka topics):

```bash
docker compose down -v
```

### Restarting Services

To restart a specific service:

```bash
docker compose restart <service-name>
```

To restart all services:

```bash
docker compose restart
```

## Common Commands Reference

| Command | Description |
|---------|-------------|
| `docker compose up -d` | Start all services in background |
| `docker compose up` | Start services and attach to logs |
| `docker compose ps` | List running services |
| `docker compose logs -f <service>` | Follow logs for a service |
| `docker compose top` | Display running processes |
| `docker compose exec <service> <command>` | Run a command in a running container |
| `docker compose down` | Stop and remove containers |
| `docker compose down -v` | Stop, remove containers and volumes |
| `docker compose pull` | Pull service images |
| `docker compose build` | Build or rebuild services |
| `docker compose config` | View the resolved Compose file |
| `docker compose port <service> <port>` | See the host port mapped to a container port |

## Troubleshooting

### Service Fails to Start

1. Check logs: `docker compose logs <service>`
2. Ensure required ports are free (e.g., 9092 for Kafka, 8000 for API)
3. For GPU services, verify NVIDIA Container Toolkit is installed and the user is in the `docker` group.

### Healthcheck Failures

Services use healthchecks to determine readiness. If a service repeatedly fails:
- Increase `start_period` in the healthcheck if the service needs more time to initialize.
- Check the service-specific logs for startup errors.

### Data Persistence

Volumes are used for persistent data (Kafka, Redis, etc.). To reset state:
```bash
docker compose down -v
```
Then restart with `docker compose up -d`.

## Notes

- The stack uses a dedicated bridge network (`cv_backbone`) for inter-service communication.
- Internal services (like Kafka broker inter-listener) use the `cv_internal` network which is isolated from the host.
- The `kafka-init` service runs once to create required Kafka topics and then exits (check its status with `docker compose ps kafka-init`).
- For development, API and Dashboard containers mount source code for hot-reloading.