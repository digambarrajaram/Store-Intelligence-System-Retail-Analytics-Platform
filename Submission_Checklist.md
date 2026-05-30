Submission Checklist
1. Title
Store Intelligence System — AI-Powered CCTV Analytics Platform
2. Description
An end-to-end AI-powered Store Intelligence System that transforms raw CCTV footage 
into real-time actionable analytics using computer vision, event streaming, and 
production-grade APIs on AWS.

**Core capabilities:**
- Real-time person detection & tracking using YOLOv8 + ByteTrack
- Zone-level footfall count, dwell time, and heatmap generation
- Anomaly detection (crowd surges, long dwell, abandoned objects, after-hours activity)
- Event streaming via Apache Kafka (MSK) with sub-2s end-to-end latency
- REST + WebSocket APIs with JWT authentication (Cognito)
- Live dashboard with real-time KPIs, heatmaps, and anomaly alerts
- Full DevOps pipeline: GitHub Actions → CodePipeline → ECS → Terraform IaC
- MLOps: nightly SageMaker retraining with canary deployment and drift monitoring

**Architecture layers:**
Ingest (KVS) → CV Pipeline (ECS GPU) → Event Streaming (MSK/Kafka) → 
Real-time Analytics (Flink SQL + Redis + OpenSearch) → API (FastAPI + API Gateway) → 
Dashboard (React + Grafana + QuickSight)

**Tech Stack:** Python, FastAPI, YOLOv8, ByteTrack, React, Terraform, 
AWS (ECS, MSK, SageMaker, Kinesis, ElastiCache, OpenSearch, Redshift, 
API Gateway, Cognito, CloudWatch, X-Ray)
3. Theme
Select: Purplle Tech Challenge 2026 — Round 2 Problem Statement (only one option)
4. Snapshots (3 images to prepare)
You need to create/screenshot these:

Image 1: Architecture diagram (export the one I generated as PNG)
Image 2: Live dashboard screenshot (React UI with heatmap + KPI cards)
Image 3: Anomaly detection output / Grafana dashboard screenshot

5. Video URL
Record a 3–5 minute Loom or YouTube demo showing:

CCTV feed being processed live
Dashboard updating in real-time
An anomaly being triggered and alerted
Briefly show the CI/CD pipeline and Terraform

Suggested format: https://www.loom.com/share/your-demo-id
6. Presentation (PDF/PPTX)
A pitch deck with these slides:

Problem statement
Solution overview
Architecture diagram
Tech stack + trade-off decisions
Live demo screenshots
SLOs and performance metrics
DevOps / MLOps pipeline
What's next / roadmap

Want me to generate this as a PPTX file?
7. Demo Link
Options depending on what you've built:

Vercel/Netlify deployed React dashboard: https://store-intel.vercel.app
Or a recorded Loom if not deployed: same as Video URL
At minimum, use a localhost ngrok tunnel during judging window

8. Repository URL
https://github.com/digambar51/store-intelligence-system
Make sure the repo has: good README (already done ✅), no video/dataset files, all source code committed.
9. Source Code (ZIP)
Zip everything except video files and dataset:
bashzip -r store-intelligence-submission.zip . \
  --exclude "*.mp4" \
  --exclude "*.avi" \
  --exclude "models/*.pt" \
  --exclude "__pycache__/*" \
  --exclude ".git/*" \
  --exclude "node_modules/*" \
  --exclude "*.egg-info/*"
10. Instructions to Run
## Prerequisites
- Docker + Docker Compose
- Python 3.11+
- Node.js 20+

## Quick Start (Local)

1. Clone the repository
   git clone https://github.com/digambar51/store-intelligence-system.git
   cd store-intelligence-system

2. Start the full local stack (Kafka, Redis, LocalStack)
   docker-compose up -d

3. Seed zone configuration
   python scripts/seed_zones.py --env local

4. Start the CV pipeline (uses sample footage)
   cd services/cv-pipeline
   pip install -r requirements.txt
   python src/frame_processor.py --source tests/sample_footage.mp4

5. Start the API
   cd services/api
   pip install -r requirements.txt
   uvicorn src.main:app --reload --port 8000
   API docs: http://localhost:8000/docs

6. Start the dashboard
   cd dashboard
   npm install && npm run dev
   Open: http://localhost:5173

## AWS Deployment (optional, requires AWS credentials)
   cd infra
   terraform init
   terraform apply -var-file=environments/dev.tfvars

Priority Order to Build First
Since the deadline is June 3, 11:59 PM IST, here's what to focus on:
PriorityWhatWhy🔴 MustWorking CV pipeline on sample videoCore of the problem🔴 MustAt least 2–3 API endpoints workingDemo Link field needs something live🔴 MustBasic React dashboard showing outputVisual impact for judges🟡 ShouldDocker Compose local setup workingInstructions to Run field🟡 ShouldPitch deck PDFPresentation field🟢 NiceTerraform IaCBonus points, DevOps maturity🟢 NiceGrafana dashboardObservability story