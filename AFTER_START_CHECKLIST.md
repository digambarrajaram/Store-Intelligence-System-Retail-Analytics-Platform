# After-Start Checklist

Use this checklist to verify that the CV Pipeline Docker Compose stack has started correctly and all services are functioning as expected.

## 1. Service Status Verification

Run `docker compose ps` and ensure all services show `State: Up` (except `kafka-init` which should exit with `State: Exited (0)` after creating topics).

Example output:
```
NAME                    COMMAND                  SERVICE             STATE              PORTS
cv_api                  "uvicorn api.main:…"     api                 Up (healthy)    0.0.0.0:8000->8000/tcp
cv_dashboard            "npm run dev -- --…"     dashboard           Up (healthy)    0.0.0.0:3000->3000/tcp
cv_grafana              "/run.sh"                grafana             Up (healthy)    0.0.0.0:3001->3000/tcp
cv_kafka                "/etc/confluent/dock…"   kafka               Up (healthy)    0.0.0.0:9092->9092/tcp, 0.0.0.0:9101->9101/tcp
cv_kafka_init           "/bin/bash -c \"\e…"     kafka-init          Exited (0)      <not set>
cv_kafka_ui             "/usr/bin/dumb-init …"   kafka-ui            Up (healthy)    0.0.0.0:8080->8080/tcp
cv_prometheus           "/bin/prometheus --c…"   prometheus          Up (healthy)    0.0.0.0:9090->9090/tcp
cv_redis                "docker-entrypoint.s…"   redis               Up (healthy)    0.0.0.0:6379->6379/tcp
cv_worker               "python /app/worker…"    worker              Up (healthy)    <not set>
cv_zookeeper            "/etc/confluent/dock…"   zookeeper           Up (healthy)    <not set>
```

## 2. Healthcheck Verification

Each service with a healthcheck should show `healthy` in the `STATE` column (as above). If any service shows `starting` or `unhealthy`, check its logs:
```bash
docker compose logs <service-name>
```

## 3. Service Accessibility

Verify that the following endpoints are accessible:

| Service | URL | Expected Response |
|---------|-----|-------------------|
| API Health | `http://localhost:8000/health` | `200 OK` with JSON `{ "status": "ok" }` |
| Kafka UI | `http://localhost:8080` | Kafka UI login page |
| Dashboard | `http://localhost:3000` | React Dashboard UI |
| Prometheus | `http://localhost:9090` | Prometheus expression browser |
| Grafana | `http://localhost:3001` | Grafana login (admin/admin) |

## 4. Internal Service Checks

### Kafka Topics
Run the following command to verify topics were created:
```bash
docker compose exec kafka kafka-topics --bootstrap-server localhost:9092 --list
```
Expected output:
```
cv.anomalies
cv.detections
cv.heartbeats
```

### Redis Connectivity
```bash
docker compose exec redis redis-cli ping
```
Expected output:
```
PONG
```

### API Dependencies
Check that the API can connect to Kafka and Redis (via health endpoint):
```bash
curl -s http://localhost:8000/health
```
Should return a JSON object indicating all dependencies are healthy.

## 5. Worker Service Verification

The worker service should be running and waiting for video input. To verify:
1. Check logs for startup messages:
   ```bash
   docker compose logs -f worker
   ```
   Look for lines indicating YOLO model loading and video source initialization.

2. If you have placed a video file in the `video_input` volume (or mounted a file), the worker should begin processing frames and publishing to Kafka topics.

## 6. Data Flow Verification (Optional)

To verify end-to-end data flow:
1. Produce a test message to the `cv.detections` topic:
   ```bash
   docker compose exec kafka kafka-console-producer --broker-list localhost:9092 --topic cv.detections <<< '{"test": "message"}'
   ```
2. Consume from the topic to confirm:
   ```bash
   docker compose exec kafka kafka-console-consumer --bootstrap-server localhost:9092 --topic cv.detections --from-beginning --max-messages 1
   ```

## 7. Resource Usage

Check that containers are not consuming excessive resources:
```bash
docker compose stats
```
Look for reasonable CPU and memory usage (especially for worker and API services).

## 8. Stopping and Restarting

After verifying the stack works, practice stopping and restarting:
```bash
docker compose stop
docker compose start
```
Then re-run this checklist to ensure services come back healthy.

## Notes

- The first startup may take several minutes as images are downloaded and services initialize.
- If you encounter issues, refer to the [Docker Compose Start Guide](./GUIDE_DOCKER_COMPOSE_START.md) for troubleshooting.
- For development, changes to API or Dashboard source code should trigger automatic reloads due to volume mounts.
- The `kafka-init` service is designed to exit after creating topics; its `Exited (0)` state is expected and indicates success.