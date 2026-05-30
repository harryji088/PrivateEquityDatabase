.PHONY: dev backend frontend seed migrate test

# Start PostgreSQL + Redis
db-up:
	docker compose up -d db redis

db-down:
	docker compose stop db redis

# Backend
backend-dev:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

backend-install:
	cd backend && pip install -e ".[dev]"

# Frontend
frontend-dev:
	cd frontend && npm run dev

frontend-install:
	cd frontend && npm install

# Database
migrate:
	cd backend && alembic upgrade head

migrate-create:
	cd backend && alembic revision --autogenerate -m "$(msg)"

seed:
	cd backend && python scripts/seed_data.py

# Run both (requires 2 terminals)
dev:
	@echo "Run 'make backend-dev' and 'make frontend-dev' in separate terminals"

# Tests
test:
	cd backend && pytest

# Docker
docker-up:
	docker compose up -d

docker-down:
	docker compose down
