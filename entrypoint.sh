#!/bin/sh
set -e

if [ -n "$CAMERA_ID" ] || [ -n "$STORE_ID" ]; then
  echo "Starting worker in single-camera mode: STORE_ID=${STORE_ID:-<none>} CAMERA_ID=${CAMERA_ID:-<none>}"
else
  echo "Starting worker in multi-camera mode (loading cameras from $CAMERA_CONFIG_PATH)"
fi

exec python worker/worker.py
