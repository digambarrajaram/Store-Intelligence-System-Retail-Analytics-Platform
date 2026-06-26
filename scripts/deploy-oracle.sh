#!/bin/bash
# ── Store Intelligence System — Oracle Cloud Deploy Script ───────────────────
# Usage: ./scripts/deploy-oracle.sh [--build|--up|--down|--logs|--health]
#
# Prerequisites:
#   - Docker and Docker Compose plugin installed
#   - This repo cloned to the Oracle Cloud VM
#   - .env file configured (copy from .env.example)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="docker-compose.oracle.yml"
PROJECT_NAME="store-intel"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Check prerequisites ─────────────────────────────────────────────────────

check_prereqs() {
  log "Checking prerequisites..."

  if ! command -v docker &>/dev/null; then
    err "Docker is not installed. Run: curl -fsSL https://get.docker.com | sudo sh"
    exit 1
  fi

  if ! docker compose version &>/dev/null; then
    err "Docker Compose plugin is not installed. Run: sudo apt-get install -y docker-compose-plugin"
    exit 1
  fi

  if [ ! -f "$REPO_DIR/$COMPOSE_FILE" ]; then
    err "Compose file not found: $REPO_DIR/$COMPOSE_FILE"
    exit 1
  fi

  if [ ! -f "$REPO_DIR/.env" ]; then
    warn ".env file not found — creating from .env.example"
    cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
  fi

  # Check if user is in docker group
  if ! docker ps &>/dev/null; then
    warn "Cannot connect to Docker daemon. Ensure your user is in the 'docker' group:"
    warn "  sudo usermod -aG docker \$USER && newgrp docker"
  fi

  log "All prerequisites met."
}

# ── Build ────────────────────────────────────────────────────────────────────

do_build() {
  log "Building Docker images for ARM64 (this will take 10-15 minutes on first run)..."
  cd "$REPO_DIR"

  # Pre-create model cache directory so YOLO download persists across rebuilds
  mkdir -p "$REPO_DIR/.model_cache"

  docker compose -f "$COMPOSE_FILE" build \
    --build-arg BUILDKIT_INLINE_CACHE=1 \
    2>&1 | tee "$REPO_DIR/build.log"

  log "Build complete."
}

# ── Start ────────────────────────────────────────────────────────────────────

do_up() {
  log "Starting Store Intelligence System..."
  cd "$REPO_DIR"

  docker compose -f "$COMPOSE_FILE" up -d

  log "Containers started. Waiting for health checks..."
  do_wait_healthy
}

# ── Stop ─────────────────────────────────────────────────────────────────────

do_down() {
  log "Stopping all services..."
  cd "$REPO_DIR"
  docker compose -f "$COMPOSE_FILE" down
  log "All services stopped."
}

# ── Logs ─────────────────────────────────────────────────────────────────────

do_logs() {
  cd "$REPO_DIR"
  docker compose -f "$COMPOSE_FILE" logs -f --tail=50
}

# ── Health Check ─────────────────────────────────────────────────────────────

do_wait_healthy() {
  local max_wait=180
  local waited=0
  local interval=5

  log "Waiting for API to become healthy (timeout: ${max_wait}s)..."

  while [ $waited -lt $max_wait ]; do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
      log "API is healthy!"
      echo
      curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || true
      echo
      log "Dashboard:  http://localhost:3000"
      log "API:        http://localhost:8000"
      log "Grafana:    http://localhost:3001 (admin/admin)"
      log "Prometheus: http://localhost:9090"
      return 0
    fi
    sleep $interval
    waited=$((waited + interval))
    echo -n "."
  done

  warn "API did not become healthy within ${max_wait}s. Check logs with: $0 --logs"
  return 1
}

do_health() {
  log "Running health check..."
  echo

  # API health
  echo -n "  API (/health):           "
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    echo -e "${GREEN}✓ OK${NC}"
  else
    echo -e "${RED}✗ FAIL${NC}"
  fi

  # Stores
  echo -n "  API (/api/v1/stores):    "
  if curl -sf http://localhost:8000/api/v1/stores >/dev/null 2>&1; then
    echo -e "${GREEN}✓ OK${NC}"
  else
    echo -e "${RED}✗ FAIL${NC}"
  fi

  # Metrics
  echo -n "  API (/api/v1/store-metrics): "
  if curl -sf http://localhost:8000/api/v1/store-metrics >/dev/null 2>&1; then
    echo -e "${GREEN}✓ OK${NC}"
  else
    echo -e "${RED}✗ FAIL${NC}"
  fi

  # Dashboard
  echo -n "  Dashboard (:3000):       "
  if curl -sf http://localhost:3000/health >/dev/null 2>&1; then
    echo -e "${GREEN}✓ OK${NC}"
  else
    echo -e "${RED}✗ FAIL${NC}"
  fi

  # Prometheus
  echo -n "  Prometheus (:9090):      "
  if curl -sf http://localhost:9090/-/healthy >/dev/null 2>&1; then
    echo -e "${GREEN}✓ OK${NC}"
  else
    echo -e "${YELLOW}~ NOT READY${NC}"
  fi

  # Grafana
  echo -n "  Grafana (:3001):         "
  if curl -sf http://localhost:3001/api/health >/dev/null 2>&1; then
    echo -e "${GREEN}✓ OK${NC}"
  else
    echo -e "${YELLOW}~ NOT READY${NC}"
  fi

  # Workers
  echo -n "  Worker store_1/cam1:    "
  if docker exec redis redis-cli get "store:store_1:camera:camera_1:worker.alive" 2>/dev/null | grep -q "1"; then
    echo -e "${GREEN}✓ OK${NC}"
  else
    echo -e "${YELLOW}~ NOT READY${NC}"
  fi

  echo -n "  Worker store_2/cam1:    "
  if docker exec redis redis-cli get "store:store_2:camera:camera_1:worker.alive" 2>/dev/null | grep -q "1"; then
    echo -e "${GREEN}✓ OK${NC}"
  else
    echo -e "${YELLOW}~ NOT READY${NC}"
  fi

  echo
  echo "  Run './scripts/deploy-oracle.sh --simulate' to populate demo data."
}

# ── Simulate Demo Data ───────────────────────────────────────────────────────

do_simulate() {
  log "Populating demo data..."
  curl -sf -X POST "http://localhost:8000/api/v1/simulate?entries=25&exits=15&anomalies=3&store_id=store_1&camera_id=camera_1" | python3 -m json.tool
  curl -sf -X POST "http://localhost:8000/api/v1/simulate?entries=18&exits=12&anomalies=2&store_id=store_2&camera_id=camera_1" | python3 -m json.tool
  log "Demo data populated. Refresh the dashboard to see live data."
}

# ── Full Deploy (build + up + simulate) ─────────────────────────────────────

do_deploy() {
  check_prereqs
  do_build
  do_up
  sleep 10
  do_simulate
  echo
  log "Deployment complete!"
  echo
  echo "  ┌─────────────────────────────────────────────┐"
  echo "  │  Dashboard:   http://localhost:3000         │"
  echo "  │  API:         http://localhost:8000         │"
  echo "  │  Grafana:     http://localhost:3001         │"
  echo "  │  Prometheus:  http://localhost:9090         │"
  echo "  │  API Docs:    http://localhost:8000/docs    │"
  echo "  └─────────────────────────────────────────────┘"
}

# ── Usage ────────────────────────────────────────────────────────────────────

usage() {
  echo "Usage: $0 [COMMAND]"
  echo
  echo "Commands:"
  echo "  --deploy      Full deployment: check, build, start, simulate (default)"
  echo "  --build       Build Docker images only"
  echo "  --up          Start all services"
  echo "  --down        Stop all services"
  echo "  --logs        Tail all logs"
  echo "  --health      Run health check on all services"
  echo "  --simulate    Populate demo data via API"
  echo "  --check       Check prerequisites only"
  echo
  echo "Examples:"
  echo "  $0 --deploy        # Fresh deploy"
  echo "  $0 --health        # Check if everything is running"
  echo "  $0 --logs          # Watch live logs"
}

# ── Main ─────────────────────────────────────────────────────────────────────

case "${1:---deploy}" in
  --deploy)   do_deploy ;;
  --build)    check_prereqs && do_build ;;
  --up)       check_prereqs && do_up ;;
  --down)     do_down ;;
  --logs)     do_logs ;;
  --health)   do_health ;;
  --simulate) do_simulate ;;
  --check)    check_prereqs ;;
  -h|--help)  usage ;;
  *)
    err "Unknown command: $1"
    usage
    exit 1
    ;;
esac
