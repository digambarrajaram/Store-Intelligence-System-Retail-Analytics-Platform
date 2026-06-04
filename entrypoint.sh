#!/bin/sh
set -e

# Wait for Redis to be ready
echo "Waiting for Redis..."
for i in $(seq 1 30); do
  if python -c "import redis; r=redis.Redis(host='${REDIS_HOST:-redis}', port=${REDIS_PORT:-6379}); r.ping()" 2>/dev/null; then
    echo "Redis is ready"
    break
  fi
  echo "Waiting for Redis... attempt $i"
  sleep 2
done

# Seed salesperson data
echo "Seeding salesperson data..."
python /app/worker/seed_salesperson.py

# Start the API
echo "Starting API server..."
exec uvicorn main:app \
     --host 0.0.0.0 \
     --port 8000 \
     --workers 1 \
     --timeout-keep-alive 30 \
     --access-log
