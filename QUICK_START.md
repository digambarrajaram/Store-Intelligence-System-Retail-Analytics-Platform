# Quick Reference: Production Updates

## 🎯 What Changed

### Backend API Routes

```
GET /api/v1/occupancy/history
  ├─ NEW ENDPOINT
  ├─ Returns: {window_minutes, interval_minutes, peak_count, history: [{timestamp, count}]}
  ├─ Max 60 points for performance
  └─ Drives: OccupancyChart area visualization

GET /api/v1/funnel
  ├─ RESPONSE FORMAT CHANGED
  ├─ Old: {entered_store: 150, browsed_gt_2min: 120, ...}
  ├─ New: [{step: "Entered Store", value: 150}, ...]
  └─ Drives: FunnelChart Recharts component

GET /api/v1/insights/salesperson?date=YYYY-MM-DD
  ├─ STATUS CODE CHANGE
  ├─ Old: 404 when no data
  ├─ New: 200 with []
  └─ Drives: SalespersonLeaderboard empty state
```

### Frontend Components

```
AnomalyFeed.tsx (Live Alerts)
  ├─ Parses WebSocket wrapper: {type, data, connected_clients, server_time}
  ├─ Shows toast notification for new anomalies (4s auto-dismiss)
  ├─ Displays alert feed (last 20)
  └─ Features: Severity badges, timestamps, auto-scroll

OccupancyChart.tsx (Historical Occupancy)
  ├─ Switched from /metrics to /occupancy/history
  ├─ Renders: AreaChart with 60-minute window
  ├─ Reference line: Peak occupancy (dashed red)
  └─ Tooltip: Timestamp + count

FunnelChart.tsx (Conversion Funnel)
  ├─ Direct consumption: [{step, value}, ...]
  ├─ No mapping needed
  └─ Recharts Funnel component
```

---

## 🚀 Deployment Quick Start

### Prerequisites
```bash
# Ensure Docker & Docker Compose installed
docker --version
docker-compose --version

# Validate composition
docker-compose config
```

### Build & Run
```bash
# Build all services
docker-compose build

# Start services (detached)
docker-compose up -d

# View logs (all services)
docker-compose logs -f

# View specific service
docker-compose logs -f api
```

### Test Endpoints
```bash
# Health check
curl http://localhost:8000/health

# Occupancy history
curl "http://localhost:8000/api/v1/occupancy/history?window_minutes=60&interval_minutes=5"

# Funnel (new format)
curl http://localhost:8000/api/v1/funnel

# Salesperson (empty check)
curl "http://localhost:8000/api/v1/insights/salesperson?date=$(date +%Y-%m-%d)"

# WebSocket test (new terminal)
wscat -c ws://localhost:8000/ws/alerts

# Send test anomaly (another terminal)
curl -X POST http://localhost:8000/api/v1/test-alert
```

### View Dashboard
```
http://localhost:3000
```

---

## 🔍 Validation Checklist

- [ ] `docker-compose config` returns valid YAML
- [ ] `python -m py_compile api/main.py api/routers/*.py` passes
- [ ] All Redis keys present (`entries`, `exits`, `funnel:*`)
- [ ] WebSocket connects: `wss://api:8000/ws/alerts`
- [ ] Occupancy chart renders with data points
- [ ] Anomaly toast appears on `/test-alert`
- [ ] Salesperson leaderboard shows empty state when no data
- [ ] Funnel shows 4-stage progression

---

## 📋 File Checklist

**Backend Modified**:
- ✅ `api/main.py` - Cleanup handler
- ✅ `api/routers/analytics.py` - New endpoint + format
- ✅ `api/routers/insights.py` - 200 empty response + Redis host
- ✅ `api/websocket.py` - (No changes, documented)

**Frontend Modified**:
- ✅ `dashboard/src/components/OccupancyChart.tsx` - New endpoint
- ✅ `dashboard/src/components/AnomalyFeed.tsx` - Toast + parsing
- ✅ `dashboard/src/hooks/useWebSocket.ts` - Wrapper type
- ✅ `dashboard/src/types/api.ts` - WebSocketEvent interface

**Documentation Created**:
- ✅ `PRODUCTION_UPDATES.md` - Full technical guide

---

## 🛠️ Troubleshooting

### Issue: "api host not found"
**Solution**: Ensure Nginx is using runtime variable substitution (check dashboard/Dockerfile)

### Issue: WebSocket connection refused
**Solution**: Verify `ws_router` is registered in api/main.py with no prefix

### Issue: Funnel component renders empty
**Solution**: Check that `/funnel` returns `[{step, value}, ...]` format (not object)

### Issue: Occupancy chart shows no data
**Solution**: Verify Redis has `entries` and `exits` sorted sets populated

### Issue: Salesperson shows error state
**Solution**: Verify endpoint returns `200 []` instead of `404` (check insights.py)

---

## 📞 Support

**Backend Issues**: Check `docker-compose logs api`
**Frontend Issues**: Check browser console + Network tab
**WebSocket Issues**: Test with `wscat` + check server logs
**Docker Issues**: Run `docker-compose ps` to check service status

---

**Last Updated**: January 2024
**Status**: ✅ Production Ready
