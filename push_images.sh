#!/bin/bash
# Run this from your project root before submitting.
# Builds and pushes all three custom images to Docker Hub.

set -e

DOCKER_USER="digya285"

echo "=== Building images ==="
docker build -t $DOCKER_USER/store-intelligence-worker:latest ./worker
docker build -t $DOCKER_USER/store-intelligence-api:latest ./api
docker build -t $DOCKER_USER/store-intelligence-dashboard:latest ./dashboard

echo "=== Pushing to Docker Hub ==="
docker push $DOCKER_USER/store-intelligence-worker:latest
docker push $DOCKER_USER/store-intelligence-api:latest
docker push $DOCKER_USER/store-intelligence-dashboard:latest

echo "=== Done! Images available at ==="
echo "  https://hub.docker.com/u/$DOCKER_USER"
echo ""
echo "Test on a clean machine with:"
echo "  docker compose pull && docker compose up -d"
