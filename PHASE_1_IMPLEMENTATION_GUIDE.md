# Phase 1 Implementation Guide: Store Intelligence System
## Target Date: 30-05-2026

This guide outlines the steps to implement Phase 1 of the Store Intelligence System, focusing on the core capabilities: video ingestion, person detection & tracking, event streaming, real-time APIs, and a live dashboard for a single store.

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Local Development Setup](#local-development-setup)
3. [Computer Vision Pipeline](#computer-vision-pipeline)
4. [Event Streaming Infrastructure](#event-streaming-infrastructure)
5. [API Service Development](#api-service-development)
6. [Dashboard Implementation](#dashboard-implementation)
7. [AWS Deployment (Optional for Phase 1)](#aws-deployment-optional-for-phase-1)
8. [Observability & Testing](#observability--testing)
9. [Phase 1 Completion Checklist](#phase-1-completion-checklist)

---

## Prerequisites

Before starting, ensure you have the following installed:

- **Docker Engine** 26.0+ (with GPU support if using NVIDIA)
- **Docker Compose** v2.20+
- **Python** 3.11+
- **Node.js** 20.x + **npm** 10.x
- **AWS CLI** v2 (if deploying to AWS)
- **Terraform** 1.7+
- **Git** 2.40+
- **NVIDIA Driver** 550+ and **CUDA Toolkit** 12.4 (for GPU acceleration)

> **Note**: For CPU-only development, the CV pipeline will fall back to OpenCV DNN or ONNX Runtime CPU, but performance will be significantly reduced.

---

## Local Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/store-intelligence.git
cd store-intelligence
```

### 2. Environment Preparation
Create a `.env` file in the root directory with the following variables (adjust as needed):
```env
# AWS (for localstack)
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_DEFAULT_REGION=us-east-1

# Kafka (Redpanda)
KAFKA_BOOTSTRAP=localhost:9092
KAFKA_TOPIC_DETECTIONS=raw.detections
KAFKA_TOPIC_EVENTS=enriched.events
KAFKA_TOPIC_ANOMALIES=anomalies

# S3 (LocalStack)
S3_FRAMES_BUCKET=store-intel-processed-frames
S3_ENDPOINT_URL=http://localhost:4566

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# Zone Configuration (DynamoDB Local)
ZONE_CONFIG_TABLE=store-zones
DYNAMODB_ENDPOINT=http://localhost:4566
```

### 3. Start Local Stack
```bash
docker-compose up -d
```
This starts:
- **Redpanda** (Kafka-compatible) on port 9092
- **Redis** on port 6379
- **LocalStack** (AWS emulation) on port 4566 (S3, DynamoDB, Kinesis, etc.)
- **Mock KVS** (via LocalStack) for video ingest simulation

### 4. Seed Initial Data
```bash
python scripts/seed_zones.py --env local
```
This creates zone configurations in DynamoDB Local for a sample store.

### 5. Prepare Sample Video
Place a sample video file (e.g., `sample_footage.mp4`) in `tests/` directory. This will be used to simulate CCTV streams.

---

## Computer Vision Pipeline

### Objective
Implement a service that consumes video frames, runs YOLOv8 detection, applies ByteTrack, assigns zones, and emits detection events to Kafka.

### Steps

#### 1. Navigate to CV Service
```bash
cd services/cv-pipeline
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```
Typical `requirements.txt`:
```
opencv-python==4.9.0.80
ultralytics==8.3.0
boto3==1.35.0
redis==5.0.0
confluent-kafka==2.4.0
numpy==2.0.0
pydantic==2.8.0
```

#### 3. Model Preparation
- Download YOLOv8n pre-trained weights: `yolov8n.pt`
- Export to ONNX for faster inference:
  ```bash
  yolo export model=yolov8n.pt format=onnx opset=13
  ```
- Place the `.onnx` file in `services/cv-pipeline/models/` (gitignored)

#### 4. Core Components
- **detector.py**: Wrapper for YOLOv8 ONNX inference with OpenCV DNN or ONNX Runtime.
- **tracker.py**: ByteTrack implementation (use `ultralytics.tracker.byte_tracker` or custom).
- **zones.py**: Load zone polygons from DynamoDB, compute point-in-polygon for track assignment.
- **event_emitter.py**: Kafka producer using `confluent_kafka.Producer` to send Avro-encoded events.
- **frame_processor.py**: Main loop that:
  1. Pulls frames from KVS (or simulated source)
  2. Runs detection → tracking
  3. For each track, assign zone and compute dwell/time
  4. Emits `raw.detections` events to Kafka
  5. Optionally writes annotated frames to S3

#### 5. Local Testing
Run the pipeline with a test video:
```bash
python src/frame_processor.py --source tests/sample_footage.mp4 --show
```
Add `--show` to display annotated frames locally.

#### 6. Dockerize
Ensure `Dockerfile` uses NVIDIA CUDA base image if GPU available:
```dockerfile
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04
# ... install dependencies, copy code, etc.
```
Build and test:
```bash
docker build -t store-intel/cv-pipeline:local .
docker run --rm --gpus all -v $(pwd)/models:/app/models store-intel/cv-pipeline:local
```

---

## Event Streaming Infrastructure

### Objective
Set up Kafka topics and schema validation for reliable event streaming.

### Steps (using LocalStack/Redpanda)

#### 1. Create Topics
```bash
# Using kcat or kafka-cli
kafka-topics --bootstrap-server localhost:9092 --create \
  --topic raw.detections --partitions 6 --replication-factor 1
kafka-topics --bootstrap-server localhost:9092 --create \
  --topic enriched.events --partitions 6 --replication-factor 1
kafka-topics --bootstrap-server localhost:9092 --create \
  --topic anomalies --partitions 3 --replication-factor 1
```

#### 2. Schema Registration (AWS Glue Schema Registry via LocalStack)
Use AWS CLI against LocalStack:
```bash
aws --endpoint-url=http://localhost:4566 glue create-schema \
  --name DetectionEventSchema \
  --data-format AVRO \
  --schema-definition file://avro/detection_event.avsc
```
Define `detection_event.avsc` matching the JSON schema in README.md.

#### 3. Configure Producer/Consumer
In the CV pipeline and anomaly detector, configure the Kafka producer/consumer to use the schema registry for serialization/deserialization.

---

## API Service Development

### Objective
Build a FastAPI service that provides REST endpoints and WebSocket streams for analytics, anomalies, and camera management.

### Steps

#### 1. Navigate to API Service
```bash
cd services/api
```

#### 2. Install Dependencies
```bash
pip install -r requirements.txt
```
Typical `requirements.txt`:
```
fastapi==0.112.0
uvicorn[standard]==0.30.1
pydantic==2.8.0
redis==5.0.0
opensearch-py==2.13.0
boto3==1.35.0
python-multipart==0.0.9
```

#### 3. Implement Core Modules
- **src/main.py**: FastAPI app setup, include routers, lifespan events for Redis/OpenSearch connections.
- **src/routers/analytics.py**: Endpoints for footfall, heatmap, dwell time.
- **src/routers/anomalies.py**: REST endpoint for anomaly queries + WebSocket for live anomaly stream.
- **src/routers/cameras.py**: CRUD for camera configurations.
- **src/routers/health.py**: Liveness and readiness probes.
- **src/services/**: Service classes for Redis (caching KPIs), OpenSearch (historical queries), DynamoDB (event store).

#### 4. OpenAPI Specification
Ensure `openapi.yaml` is kept up-to-date with the implemented endpoints. Use tools like `fastapi-code-generator` if needed.

#### 5. Local Testing
Start the API:
```bash
uvicorn src.main:app --reload --port 8000
```
Test endpoints via `http://localhost:8000/docs`.

#### 6. Dockerize
```dockerfile
FROM python:3.11-slim
# ... install dependencies, copy code
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "80"]
```
Build and run:
```bash
docker build -t store-intel/api:local .
docker run -p 8000:80 --env-file ../.env store-intel/api:local
```

---

## Dashboard Implementation

### Objective
Create a React dashboard that visualizes live KPIs, heatmaps, footfall charts, and anomaly feeds via WebSocket.

### Steps

#### 1. Navigate to Dashboard
```bash
cd dashboard
```

#### 2. Install Dependencies
```bash
npm install
```
Typical `package.json` dependencies:
```
"react": "^18.3.0",
"react-dom": "^18.3.0",
"vite": "^5.4.0",
"recharts": "^2.13.0",
"socket.io-client": "^4.7.5"
```

#### 3. Implement Core Components
- **src/components/KPICards.jsx**: Displays live footfall, average dwell, current occupancy.
- **src/components/FootfallChart.jsx**: Line chart showing footfall over time (uses Recharts).
- **src/components/HeatmapView.jsx**: Grid-based heatmap using CSS or SVG.
- **src/components/AnomalyFeed.jsx**: Real-time list of anomalies from WebSocket.
- **src/hooks/useWebSocket.js**: Custom hook for managing WebSocket connection to `/stream/anomalies`.
- **src/hooks/useAnalytics.js**: Hooks for fetching analytics data via REST.

#### 4. Main App
**src/App.jsx**: Layout with sidebar (store/camera selector) and main panel rotating through views.

#### 5. Local Development
Start the Vite dev server:
```bash
npm run dev
```
Dashboard available at `http://localhost:5173`.

#### 6. Dockerize (for production)
```dockerfile
FROM node:20-alpine AS builder
# ... install deps, build
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
```
Build and test:
```bash
npm run build
docker build -t store-intel/dashboard:local .
docker run -p 8080:80 store-intel/dashboard:local
```

---

## AWS Deployment (Optional for Phase 1)

If you wish to deploy Phase 1 to AWS for an end-to-end test, follow these steps.

### 1. Prerequisites
- AWS account with permissions to create resources.
- Terraform configured with backend (S3 + DynamoDB lock).
- GitHub Actions secrets set (if using CI/CD).

### 2. Provision Infrastructure
```bash
cd infra
terraform init -backend-config=environments/dev.tfvars
terraform plan -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars
```
This creates VPC, ECS cluster, MSK, Redis, OpenSearch, etc.

### 3. Build and Push Images
```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push each service
docker build -t <account-id>.dkr.ecr.us-east-1.amazonaws.com/store-intel/cv-pipeline:latest services/cv-pipeline
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/store-intel/cv-pipeline:latest
# Repeat for api and dashboard
```

### 4. Deploy Services
```bash
# Update ECS services to use new image
aws ecs update-service --cluster store-intel --service cv-pipeline --force-new-deployment
aws ecs update-service --cluster store-intel --service api --force-new-deployment
```
Dashboard is deployed via S3 + CloudFront:
```bash
cd dashboard
npm run build
aws s3 sync dist/ s3://<dashboard-bucket> --delete
aws cloudfront create-invalidation --distribution-id <dist-id> --paths "/*"
```

### 5. Configure DNS (Optional)
Use Route 53 to point `api.storeintel.example.com` and `dashboard.storeintel.example.com` to the ALB/CloudFront distributions.

---

## Observability & Testing

### 1. Logging
- Ensure all services log to stdout (captured by Docker/ECS).
- Use structured logging (JSON) for easy parsing.

### 2. Metrics
- **CV Pipeline**: Export frame processing latency, detection count, GPU utilization to CloudWatch Embedded Metric Format.
- **API**: Instrument with Prometheus client (expose `/metrics` endpoint) or use X-Ray traces.
- **Dashboard**: Use browser vitals (LCP, FID) via web-vitals library.

### 3. Testing
- **Unit Tests**: Write pytest tests for Python services, Jest/Vitest for React components.
- **Integration Tests**: Use `docker-compose` to spin up full stack and test end-to-end flows.
- **Load Testing**: Use `k6` script in `scripts/load_test.sh` to simulate multiple cameras.

### 4. Health Checks
- Implement `/health` endpoints returning 200 if dependencies (Kafka, Redis, DB) are reachable.
- Use ECS service load balancer health checks.

---

## Phase 1 Completion Checklist

- [ ] Local development stack runs without errors (docker-compose up)
- [ ] CV pipeline processes video and emits detection events to Kafka
- [ ] Kafka topics are created and receiving Avro-encoded events
- [ ] API service starts and serves REST endpoints (footfall, anomalies, cameras)
- [ ] Dashboard loads and displays live data via WebSocket and REST
- [ ] Anomaly detector consumer runs and logs scores (optional for Phase 1)
- [ ] All services have Dockerfiles and can be run containerized
- [ ] Basic observability: logs visible, health checks responding
- [ ] (Optional) AWS deployment successful and services reachable via public endpoints

---

## Next Steps (Phase 2)
After completing Phase 1, consider:
- Adding multi-store support with dynamic zone configuration.
- Implementing model retraining pipeline with SageMaker.
- Enhancing anomaly detection with deep learning models.
- Adding advanced analytics: conversion rates, queue detection, staff detection.
- Implementing role-based access control (RBAC) in Cognito.
- Setting up CI/CD pipelines with GitHub Actions and ArgoCD.

--- 
*Guide generated on 30-05-2026. Adjust versions and commands as per the latest releases at that time.*