# 🏪 Store Intelligence System
### Purplle Tech Challenge 2026 — Round 2

An end-to-end AI-powered Store Intelligence System built on AWS that transforms raw CCTV footage into real-time analytics, anomaly detection, and actionable business intelligence.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Services](#services)
- [AWS Infrastructure](#aws-infrastructure)
- [DevOps Pipeline](#devops-pipeline)
- [MLOps Pipeline](#mlops-pipeline)
- [Event Schema](#event-schema)
- [API Reference](#api-reference)
- [Observability](#observability)
- [Local Development](#local-development)
- [Deployment](#deployment)
- [SLOs & Performance](#slos--performance)
- [Trade-off Decisions](#trade-off-decisions)

---

## Overview

This system ingests live CCTV video streams from retail stores, runs a computer vision detection and tracking pipeline, streams structured events through Kafka, and serves real-time analytics via production-grade APIs and a live dashboard.

**Core capabilities:**

| Capability | Description |
|---|---|
| Person detection & tracking | YOLOv8 + ByteTrack with persistent `track_id` across frames |
| Zone intelligence | Dwell time, footfall count, heatmaps per store zone |
| Anomaly detection | Crowd surges, abandoned objects, unusual dwell patterns |
| Real-time streaming | Sub-2s end-to-end latency from frame capture to alert |
| Live dashboard | WebSocket-powered KPIs, heatmaps, and anomaly alerts |
| Production APIs | REST + WebSocket, JWT auth, rate limiting, OpenAPI spec |

---

## Architecture

```
CCTV Cameras (RTSP)
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  INGEST LAYER                                               │
│  Kinesis Video Streams → S3 Raw → CloudFront               │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  AI / CV PIPELINE (ECS Fargate GPU)                        │
│  YOLOv8 Detection → ByteTrack → SageMaker Endpoint        │
│  Anomaly Detector (Lambda)   → S3 Processed Frames        │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  EVENT STREAMING (Amazon MSK / Kafka)                       │
│  raw.detections → enriched.events → anomalies              │
│  EventBridge → SNS/SQS fanout                             │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  REAL-TIME ANALYTICS                                        │
│  Kinesis Flink SQL → OpenSearch → ElastiCache Redis       │
│  Redshift (warehouse)                                      │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  API LAYER                                                  │
│  API Gateway (REST + WebSocket) → FastAPI on ECS           │
│  Cognito JWT Auth → WAF + Shield                          │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  DASHBOARD                                                  │
│  React + Vite → S3 + CloudFront → Grafana → QuickSight    │
└─────────────────────────────────────────────────────────────┘
```

Full architecture diagram with all AWS service connections: [`docs/architecture.png`](docs/architecture.png)

---

## Tech Stack

### AI / ML

| Component | Technology | Reason |
|---|---|---|
| Object detection | YOLOv8 (Ultralytics) | Best accuracy/speed tradeoff at CCTV resolution |
| Multi-object tracking | ByteTrack | State-of-the-art tracking, handles occlusion better than DeepSORT |
| Model serving | AWS SageMaker | Decouples model lifecycle from application deployment |
| Model format | ONNX / TorchScript | 3–5× inference speedup over plain PyTorch |
| Anomaly detection | Isolation Forest + rule engine | Interpretable, low-latency, no GPU required |

### AWS Services

| Layer | Service |
|---|---|
| Video ingest | Kinesis Video Streams |
| Object storage | S3 (raw, processed, models) |
| Container compute | ECS Fargate (GPU g5 instances) |
| Event streaming | Amazon MSK (Kafka) |
| Stream processing | Kinesis Data Analytics (Flink SQL) |
| Search & analytics | Amazon OpenSearch |
| Live state cache | ElastiCache (Redis) |
| Data warehouse | Amazon Redshift |
| API gateway | Amazon API Gateway |
| Auth | Amazon Cognito |
| Security | WAF, Shield, VPC, IAM |
| CI/CD | GitHub Actions |
| IaC | Terraform |
| Observability | CloudWatch, X-Ray, Prometheus, Grafana |

### Application Stack

| Component | Technology |
|---|---|
| CV service | Python 3.11, OpenCV, Ultralytics |
| API service | FastAPI, Pydantic v2 |
| Stream processor | Apache Flink SQL |
| Dashboard | React 18, Vite, Recharts, WebSocket |
| IaC | Terraform 1.7 |
| Containerization | Docker, ECR |
| GitOps | ArgoCD |

---

## Project Structure

```
store-intelligence/
│
├── infra/                          # Terraform modules (IaC)
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── modules/
│   │   ├── vpc/                    # VPC, subnets, NAT, SGs
│   │   ├── ecs/                    # ECS cluster, task defs, autoscaling
│   │   ├── msk/                    # Kafka cluster + schema registry
│   │   ├── sagemaker/              # Inference endpoint + model registry
│   │   ├── kinesis/                # KVS + KDA Flink
│   │   ├── redis/                  # ElastiCache cluster
│   │   ├── opensearch/             # OpenSearch domain
│   │   ├── redshift/               # Warehouse cluster
│   │   ├── api-gateway/            # REST + WebSocket APIs
│   │   ├── cognito/                # User pools + app clients
│   │   └── monitoring/             # CloudWatch dashboards + alarms
│   └── environments/
│       ├── dev.tfvars
│       ├── staging.tfvars
│       └── prod.tfvars
│
├── services/
│   ├── cv-pipeline/                # Core computer vision service
│   │   ├── src/
│   │   │   ├── detector.py         # YOLOv8 inference wrapper
│   │   │   ├── tracker.py          # ByteTrack integration
│   │   │   ├── event_emitter.py    # Kafka producer
│   │   │   ├── frame_processor.py  # Main pipeline orchestrator
│   │   │   └── zones.py            # Zone config + geometry logic
│   │   ├── models/                 # ONNX model files (gitignored)
│   │   ├── tests/
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── api/                        # FastAPI application
│   │   ├── src/
│   │   │   ├── main.py
│   │   │   ├── routers/
│   │   │   │   ├── analytics.py    # Footfall, dwell, heatmap endpoints
│   │   │   │   ├── anomalies.py    # Anomaly query + WebSocket
│   │   │   │   ├── cameras.py      # Camera management
│   │   │   │   └── health.py       # Health + readiness probes
│   │   │   ├── services/
│   │   │   │   ├── redis_service.py
│   │   │   │   ├── opensearch_service.py
│   │   │   │   └── dynamo_service.py
│   │   │   └── models/             # Pydantic schemas
│   │   ├── openapi.yaml            # Full OpenAPI 3.0 spec
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   │
│   ├── anomaly-detector/           # Anomaly scoring service
│   │   ├── src/
│   │   │   ├── scorer.py           # Isolation Forest + rules
│   │   │   ├── consumer.py         # Kafka consumer
│   │   │   └── alerter.py          # EventBridge publisher
│   │   └── Dockerfile
│   │
│   └── stream-processor/           # Flink SQL jobs
│       ├── jobs/
│       │   ├── footfall_windowed.sql
│       │   ├── dwell_aggregation.sql
│       │   └── zone_heatmap.sql
│       └── deploy.sh
│
├── dashboard/                      # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── HeatmapView.jsx
│   │   │   ├── FootfallChart.jsx
│   │   │   ├── AnomalyFeed.jsx
│   │   │   └── KPICards.jsx
│   │   ├── hooks/
│   │   │   ├── useWebSocket.js
│   │   │   └── useAnalytics.js
│   │   └── App.jsx
│   ├── Dockerfile
│   └── package.json
│
├── mlops/                          # SageMaker pipeline definitions
│   ├── pipeline.py                 # Retraining pipeline definition
│   ├── evaluate.py                 # mAP evaluation script
│   ├── register_model.py           # Model registry push
│   └── canary_deploy.py            # Canary traffic shift
│
├── .github/
│   └── workflows/
│       ├── ci.yml                  # Lint, test, SAST on every PR
│       ├── build-push.yml          # Build + push to ECR on merge
│       └── deploy-prod.yml         # Terraform apply + ECS deploy
│
├── scripts/
│   ├── seed_zones.py               # Seed zone config to DynamoDB
│   ├── simulate_stream.py          # Local RTSP stream simulator
│   └── load_test.sh                # k6 load test script
│
├── docker-compose.yml              # Full local stack (mock KVS, Kafka, Redis)
├── docker-compose.override.yml     # Dev overrides
├── ARCHITECTURE.md                 # Design decisions + trade-offs
├── RUNBOOK.md                      # On-call runbook
└── README.md                       # This file
```

---

## Services

### CV Pipeline (`services/cv-pipeline`)

Runs on ECS Fargate GPU instances. Consumes from Kinesis Video Streams, runs YOLOv8 detection, applies ByteTrack, and emits structured events to MSK.

**Processing flow:**

```
KVS Frame → Decode → YOLOv8 Detect → ByteTrack → Zone Assignment → Kafka Emit
                                                         │
                                                    S3 (annotated frame archive)
```

**Environment variables:**

```env
KVS_STREAM_ARN=arn:aws:kinesisvideo:...
SAGEMAKER_ENDPOINT=store-intel-yolo-endpoint
KAFKA_BOOTSTRAP=broker1:9092,broker2:9092
KAFKA_TOPIC_DETECTIONS=raw.detections
S3_FRAMES_BUCKET=store-intel-processed-frames
ZONE_CONFIG_TABLE=store-zones
```

### API Service (`services/api`)

FastAPI application behind API Gateway. Reads from Redis (live KPIs), OpenSearch (historical queries), and DynamoDB (event store).

**Start locally:**

```bash
cd services/api
uvicorn src.main:app --reload --port 8000
```

### Anomaly Detector (`services/anomaly-detector`)

Consumes `enriched.events` from Kafka. Scores each event using an Isolation Forest model trained on normal store patterns. Publishes anomalies to EventBridge, which fans out to SNS → push notification.

**Anomaly types detected:**

| Type | Trigger condition |
|---|---|
| `CROWD_SURGE` | Zone density > 2σ above rolling mean |
| `LONG_DWELL` | Single `track_id` in zone > 15 minutes |
| `ABANDONED_OBJECT` | Stationary bounding box with no associated person for > 5 minutes |
| `AFTER_HOURS` | Motion detected outside configured store hours |

---

## AWS Infrastructure

All resources are provisioned via Terraform. State is stored in S3 with DynamoDB lock.

```bash
cd infra

# Initialise
terraform init -backend-config=environments/prod.tfvars

# Plan
terraform plan -var-file=environments/prod.tfvars

# Apply
terraform apply -var-file=environments/prod.tfvars
```

### Key resource decisions

**ECS Fargate (g5.xlarge) vs EC2 GPU instances:** Fargate removes cluster management overhead. g5.xlarge gives 1× A10G GPU sufficient for real-time YOLOv8n inference at 15 fps per camera. At >20 cameras, switch to EC2 with spot instances for cost.

**MSK (Kafka) vs SQS/SNS:** Kafka provides ordered, replayable event streams with consumer group semantics — critical for backfilling analytics after a downstream outage. SQS is fire-and-forget. MSK adds operational cost but is non-negotiable for this use case.

**ElastiCache Redis vs DynamoDB for live KPIs:** Redis at sub-millisecond read latency is essential for the dashboard polling at 1s intervals. DynamoDB at 10–50ms would create visible lag. Redis is the right tool for ephemeral, high-frequency reads.

---

## DevOps Pipeline

```
Developer → git push → GitHub PR
                          │
                    GitHub Actions (CI)
                    ├── ruff lint (Python)
                    ├── pytest (unit + integration)
                    ├── Trivy (Docker image scan)
                    └── Bandit (Python SAST)
                          │
                    Merge to main
                          │
                    AWS CodePipeline
                    ├── CodeBuild → docker build → ECR push
                    ├── Terraform plan (auto)
                    ├── Manual approval gate (prod only)
                    └── ECS rolling deploy (zero downtime)
                          │
                    ArgoCD (GitOps)
                    └── Reconciles ECS task definitions
```

### GitHub Actions — CI (`ci.yml`)

```yaml
on: [pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: ruff check .
      - run: pytest tests/ --cov=src --cov-report=xml
      - uses: aquasecurity/trivy-action@master
        with: { image-ref: "${{ env.ECR_REPO }}:${{ github.sha }}" }
```

### Deployment environments

| Environment | Trigger | Approval |
|---|---|---|
| `dev` | Every merge to `develop` | Auto |
| `staging` | Every merge to `main` | Auto |
| `prod` | Manual promote from staging | Required |

---

## MLOps Pipeline

Model retraining runs nightly via **SageMaker Pipelines**.

```
Nightly trigger (EventBridge Scheduler)
       │
       ▼
SageMaker Pipeline
├── Step 1: Data extraction (last 24h hard negatives from S3)
├── Step 2: Preprocessing (frame sampling, augmentation)
├── Step 3: Training (YOLOv8 fine-tune, 50 epochs)
├── Step 4: Evaluation (mAP@0.5 on holdout set)
│           └── Gate: only proceed if mAP improves > 2%
├── Step 5: Register model to SageMaker Model Registry
└── Step 6: Canary deploy (5% traffic → new endpoint)
            └── Promote to 100% if p99 latency < 300ms after 1h
```

Experiment tracking: **MLflow** hosted on ECS. Every run logs hyperparameters, mAP, inference latency, and the ONNX model artifact.

Model drift monitoring: **CloudWatch custom metric** tracks detection confidence distribution. Alert fires if mean confidence drops > 10% from baseline (signals camera angle change or model degradation).

---

## Event Schema

Every detection event published to `raw.detections`:

```json
{
  "event_id": "a3f8c21d-4b7e-4f2a-b9c1-d82e7f3a1c00",
  "schema_version": "1.0",
  "camera_id": "store-1-cam-3",
  "store_id": "store-1",
  "timestamp": "2026-05-30T14:32:01.123Z",
  "track_id": "t-4892",
  "event_type": "ZONE_ENTRY",
  "zone": "aisle-3",
  "bbox": { "x": 120, "y": 80, "w": 60, "h": 180 },
  "confidence": 0.94,
  "frame_id": 84729,
  "metadata": {
    "dwell_seconds": 0,
    "direction": "north",
    "crowd_density": 0.32
  }
}
```

`event_type` values: `PERSON_DETECTED`, `ZONE_ENTRY`, `ZONE_EXIT`, `DWELL`, `ANOMALY`, `AFTER_HOURS`

Schema is registered and validated via **AWS Glue Schema Registry** (Avro). Producers that fail schema validation are rejected at the Kafka broker level.

---

## API Reference

Base URL: `https://api.storeintel.purplle.com/v1`

Authentication: `Authorization: Bearer <cognito_jwt>`

### REST Endpoints

```
GET  /analytics/footfall
     ?store_id=store-1
     &zone=aisle-3
     &window=1h|24h|7d
     → { zone, footfall_count, peak_time, avg_dwell_seconds }

GET  /analytics/heatmap
     ?store_id=store-1
     &from=2026-05-30T00:00:00Z
     &to=2026-05-30T23:59:59Z
     → { grid: [[density]], resolution: "1m" }

GET  /anomalies
     ?store_id=store-1
     &severity=HIGH
     &limit=50
     → { anomalies: [...], total, next_cursor }

GET  /cameras
     → { cameras: [{ camera_id, store_id, zone, status }] }

GET  /health
     → { status: "ok", version, uptime_seconds }
```

### WebSocket

```
WS  /stream/anomalies?store_id=store-1&token=<jwt>

Server pushes:
{
  "type": "ANOMALY",
  "payload": {
    "anomaly_id": "...",
    "type": "CROWD_SURGE",
    "zone": "entrance",
    "severity": "HIGH",
    "timestamp": "2026-05-30T14:32:01Z",
    "camera_id": "store-1-cam-1"
  }
}
```

Full OpenAPI 3.0 spec: [`services/api/openapi.yaml`](services/api/openapi.yaml)

---

## Observability

### Metrics

| Metric | Source | Alert threshold |
|---|---|---|
| Frame processing latency | CloudWatch (ECS) | p99 > 500ms |
| Kafka consumer lag | CloudWatch (MSK) | > 10,000 messages |
| API p99 latency | X-Ray | > 200ms |
| GPU utilization | Prometheus | < 20% (underprovisioned) or > 95% |
| Anomaly alert delivery time | CloudWatch | > 5s end-to-end |
| Model confidence mean | CloudWatch custom | Drop > 10% from baseline |

### Dashboards

- **Grafana**: Real-time ECS GPU, Kafka lag, API latency — ops team
- **CloudWatch**: Log Insights queries, alarm history — on-call
- **QuickSight**: Weekly footfall trends, zone performance — business team
- **Application dashboard**: React live view — store managers

### Distributed Tracing

X-Ray traces every request across: `API Gateway → FastAPI → Redis → OpenSearch → DynamoDB`

Trace sampling rate: 5% in prod, 100% in dev/staging.

---

## Local Development

**Prerequisites:** Docker, Docker Compose, Python 3.11, Node 20

```bash
# Clone
git clone https://github.com/your-username/store-intelligence.git
cd store-intelligence

# Start full local stack
# Includes: Kafka (Redpanda), Redis, mock KVS, LocalStack (AWS emulation)
docker-compose up -d

# Seed zone configuration
python scripts/seed_zones.py --env local

# Start CV pipeline (requires a webcam or test video)
cd services/cv-pipeline
pip install -r requirements.txt
python src/frame_processor.py --source tests/sample_footage.mp4

# Start API
cd services/api
pip install -r requirements.txt
uvicorn src.main:app --reload

# Start dashboard
cd dashboard
npm install
npm run dev
# → http://localhost:5173

# Simulate RTSP streams (no camera needed)
python scripts/simulate_stream.py --cameras 3 --video tests/sample_footage.mp4
```

**Local stack ports:**

| Service | Port |
|---|---|
| Kafka (Redpanda) UI | 8080 |
| Redis | 6379 |
| API | 8000 |
| Dashboard | 5173 |
| LocalStack | 4566 |

---

## Deployment

### Prerequisites

- AWS CLI configured with appropriate IAM role
- Terraform 1.7+
- Docker
- `GITHUB_TOKEN`, `AWS_ACCOUNT_ID` set in GitHub Secrets

### First-time setup

```bash
# 1. Bootstrap Terraform state backend
aws s3 mb s3://store-intel-terraform-state
aws dynamodb create-table \
  --table-name store-intel-tf-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# 2. Provision infrastructure
cd infra
terraform init
terraform apply -var-file=environments/prod.tfvars

# 3. Push initial Docker images to ECR
./scripts/build-and-push.sh

# 4. Deploy ECS services
aws ecs update-service --cluster store-intel --service cv-pipeline --force-new-deployment
aws ecs update-service --cluster store-intel --service api --force-new-deployment

# 5. Deploy dashboard
cd dashboard && npm run build
aws s3 sync dist/ s3://store-intel-dashboard --delete
aws cloudfront create-invalidation --distribution-id $CF_DIST_ID --paths "/*"
```

### Rollback

```bash
# ECS rollback to previous task definition
aws ecs update-service \
  --cluster store-intel \
  --service api \
  --task-definition api:$PREVIOUS_REVISION

# Terraform rollback
git revert HEAD && git push  # triggers pipeline with prior infra state
```

---

## SLOs & Performance

| SLO | Target | Measurement |
|---|---|---|
| API p99 latency | < 200ms | X-Ray |
| Detection pipeline end-to-end | < 2s | CloudWatch custom metric |
| Anomaly alert delivery | < 5s from event | EventBridge → SNS timestamp diff |
| System availability | 99.9% | CloudWatch availability alarm |
| Dashboard load time | < 2s (LCP) | CloudFront + Lighthouse CI |

**Scaling targets:**

- CV pipeline autoscales from 2 to 20 ECS tasks based on KVS shard count
- API autoscales from 2 to 50 ECS tasks based on API Gateway request rate
- MSK scales broker storage automatically; partition count is set to 30 for `raw.detections`

---

## Trade-off Decisions

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for full rationale. Summary:

| Decision | Chosen | Rejected | Reason |
|---|---|---|---|
| Tracking algorithm | ByteTrack | DeepSORT | ByteTrack handles high occlusion better; no re-id model needed |
| Detection model | YOLOv8n (ONNX) | Detectron2, RT-DETR | Best latency for real-time CCTV; ONNX gives 3× speedup |
| Event bus | MSK (Kafka) | SQS, SNS | Ordered, replayable streams; consumer group semantics for backfill |
| Live state store | Redis | DynamoDB | Sub-ms reads for 1s dashboard polling; DynamoDB adds visible lag |
| Compute | ECS Fargate | EKS, Lambda | Lower ops overhead; GPU Fargate available; Lambda cold start kills latency |
| IaC | Terraform | CDK, SAM | Multi-service, multi-account; Terraform has broadest AWS resource coverage |
| Model serving | SageMaker | Triton, TorchServe | Managed lifecycle, A/B routing, built-in monitoring |

---

## Contributing

1. Branch from `develop`: `git checkout -b feat/your-feature`
2. All commits follow Conventional Commits: `feat:`, `fix:`, `chore:`
3. PRs require: passing CI, 1 reviewer approval, no Trivy HIGH findings
4. Merge to `develop` → auto-deploy to dev environment
5. Promote to `main` → staging → manual approval → prod

---

## License

This project was built for the Purplle Tech Challenge 2026, Round 2. All code is original and developed during the hackathon period.

---

<div align="center">
  Built with ❤️ for Purplle Tech Challenge 2026
</div>
