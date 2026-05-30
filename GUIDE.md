# Store Intelligence System - Hackathon Submission Guide

## Core Philosophy: Two-Tier Architecture

**Run a lightweight local/free demo for submission, but design and document the full AWS architecture for production.** Judges evaluate your thinking, not your AWS bill.

| What You SHOW (Demo) | What You DOCUMENT (Architecture) |
|----------------------|----------------------------------|
| Docker Compose locally | Full AWS diagram + Terraform IaC |
| Sample video file | Kinesis Video Streams |
| Redpanda (free Kafka) | Amazon MSK |
| Redis OSS | ElastiCache |
| SQLite / JSON files | DynamoDB + OpenSearch |
| FastAPI localhost | ECS Fargate + API Gateway |
| React on Vercel (free) | S3 + CloudFront |

## Cost Reality Check

Running full AWS stack 24/7 costs ~$44-50/day (~$200+ for hackathon window). Not feasible.

**Smart Alternatives:**
- **Docker Compose (Recommended)**: Everything runs locally with one command
- **Free Cloud Tiers**: Vercel + Railway + Upstash (near-zero cost)
- **AWS with Controls**: Spot instances + scheduled shutdown (~$8-12 for 48h)

## Recommended Build Order (4-Day Plan)

### DAY 1 (Today): Get SOMETHING Working End-to-End Locally
- Set up project repo with defined structure
- Create `docker-compose.yml` with Kafka + Redis + API skeleton
- Build CV pipeline that reads sample .mp4 and prints detections
- Implement basic FastAPI with `/health` and one `/analytics` endpoint

### DAY 2: Core Features Working, Dashboard Visible
- YOLOv8 detection properly emitting events to Kafka
- React dashboard showing live footfall count + basic heatmap
- WebSocket connected (anomaly alerts appearing live)
- Anomaly detector triggering on simple rules

### DAY 3: Polish + Deploy Free-Tier Live Demo
- Deploy dashboard to Vercel
- Deploy API to Railway
- Connect Upstash Redis + Kafka
- Record 3-min Loom demo video
- Write ARCHITECTURE.md (trade-off decisions)

### DAY 4: DevOps Layer + Submission Polish
- GitHub Actions CI/CD working (ci.yml at minimum)
- Terraform code written (doesn't need to actually apply)
- README finalized
- Submission form filled
- Submit before 11 PM (buffer for issues)

### DAY 5 (Buffer): Emergency Fixes Only
- Do not start new features

## Why NOT AWS First?

| AWS-First Approach | Local-First Approach |
|--------------------|----------------------|
| Day 1: Setting up IAM, VPC, security groups... | Day 1: CV pipeline detecting people in video ✓ |
| Day 2: MSK not connecting, debugging CIDR blocks... | Day 2: Dashboard showing live heatmap ✓ |
| Day 3: SageMaker endpoint timeout issues... | Day 3: Deployed on Vercel, demo link ready ✓ |
| Day 4: Still debugging, nothing to submit | Day 4: Writing ARCHITECTURE.md, polishing submission ✓ |

**AWS infrastructure debugging is a time sink.** ECS networking, MSK broker configs, IAM permission errors — each can eat 3-4 hours. You cannot afford that in a 4-day hackathon.

## What Makes a "Perfect Submission"

### TIER 1 — Must Have (Eliminates You If Missing)
- ✅ Working demo link (even if localhost on video)
- ✅ GitHub repo with real code (not empty folders)
- ✅ CV pipeline actually detecting people in footage
- ✅ At least 3 API endpoints returning real data
- ✅ README with run instructions that actually work

### TIER 2 — Differentiates You From 80% of Submissions
- ✅ Live dashboard with WebSocket real-time updates
- ✅ Anomaly detection triggering and alerting
- ✅ ARCHITECTURE.md with trade-off reasoning
- ✅ GitHub Actions CI running (green checkmarks visible)
- ✅ Event schema documented

### TIER 3 — Puts You in Top 5%
- ✅ Terraform IaC written (even if not applied)
- ✅ MLOps pipeline described with SageMaker
- ✅ SLOs defined with measurement approach
- ✅ docker-compose works in one command
- ✅ Loom video showing everything working

## Priority Stack to Build (Start Here Today)

```
Sample .mp4 footage
           │
           ▼
cv-pipeline (Python + YOLOv8)  ← emits JSON events
           │
           ▼
Redpanda/Kafka (Docker)       ← consumed by
           │
           ▼
FastAPI (Python)              ← reads from Redis for live state
           │
           ▼
React Dashboard               ← WebSocket for live anomaly feed
```

## Getting Sample Footage

```bash
# Option 1: Oxford Town Centre dataset (free)
wget https://www.robots.ox.ac.uk/ActiveVision/Research/Projects/2009bbenfold_headpose/Datasets/TownCentreXVID.avi

# Option 2: YouTube video (install yt-dlp first)
pip install yt-dlp
yt-dlp "https://youtube.com/watch?v=..." -o sample_footage.mp4

# Option 3: Generate synthetic footage
python scripts/generate_synthetic.py  # draw random bounding boxes
```

## The Single Most Important Thing

**Record your Loom video on Day 3, not at the end.** Even if something breaks on Day 4, you have a working demo video. The video field is your safety net.

### Video Script (3 Minutes):
- **0:00–0:30**: Architecture diagram + 3-sentence explanation
- **0:30–1:30**: Dashboard live — people detected, footfall count up, heatmap updating
- **1:30–2:00**: Trigger anomaly manually, show real-time alert
- **2:00–2:30**: GitHub repo — folder structure, CI green, CV pipeline code
- **2:30–3:00**: `docker-compose up` working from scratch

## Immediate Next Steps (First 30 Minutes)

```bash
mkdir store-intelligence-system && cd store-intelligence-system
git init

# Create folder structure
mkdir -p services/cv-pipeline/src
mkdir -p services/api/src/routers
mkdir -p services/anomaly-detector/src
mkdir -p dashboard/src/components
mkdir -p infra/modules
mkdir -p mlops
mkdir -p .github/workflows
mkdir -p scripts
mkdir -p sample

# Add initial files (workflow, README would go here)
git add . && git commit -m "chore: initial project scaffold"
git remote add origin https://github.com/digambar51/store-intelligence-system.git
git push -u origin main
```

## Key Message for Judges (Include in README/ARCHITECTURE.md)

> ## Demo vs Production Architecture
> 
> The live demo runs on a cost-optimised stack (Vercel + Railway + Upstash free tiers + CPU inference) to avoid unnecessary cloud spend during the evaluation window. The full production architecture is documented in ARCHITECTURE.md and provisioned via Terraform IaC in the `/infra` directory. All AWS service choices, event schemas, API contracts, and DevOps pipelines are production-ready and would run identically on the full AWS stack.
> 
> Judges at a hackathon 100% understand this. What they're evaluating is your architectural thinking, code quality, and system design — not whether you burned $200 on AWS for 5 days.