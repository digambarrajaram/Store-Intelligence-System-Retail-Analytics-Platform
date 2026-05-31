.PHONY: up down logs restart-worker shell-api shell-redis

# Start all services
up:
	docker compose up -d

# Stop and remove all services, networks, and volumes
down:
	docker compose down -v

# View logs from all services (follow)
logs:
	docker compose logs -f

# Restart only the worker service
restart-worker:
	docker compose restart worker

# Open a shell in the API service container
shell-api:
	docker compose exec api /bin/sh

# Open a shell in the Redis service container
shell-redis:
	docker compose exec redis redis-cli