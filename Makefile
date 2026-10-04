.PHONY: up down build logs test test-backend test-frontend lint format clean dev migrate bootstrap frontend-lock

up: frontend-lock
	docker compose up --build -d

dev: frontend-lock
	docker compose -f compose.yaml -f compose.dev.yaml --profile dev up --build

down:
	docker compose down

build: frontend-lock
	docker compose build

frontend-lock:
	docker compose --profile tools run --rm frontend-lock

logs:
	docker compose logs -f

migrate:
	docker compose --profile tools run --rm migrate

bootstrap:
	docker compose run --rm api python -m app.bootstrap_admin

test: test-backend test-frontend

test-backend:
	@status=0; docker compose --profile test run --build --rm backend-tests || status=$$?; docker compose --profile test stop test-db >/dev/null || status=$$?; exit $$status

test-frontend: frontend-lock
	docker compose --profile test run --build --rm --no-deps frontend-tests

lint: frontend-lock
	docker compose --profile test run --build --rm --no-deps backend-tests ruff check app tests
	docker compose --profile test run --build --rm --no-deps frontend-tests npm run lint

format:
	docker compose --profile test run --build --rm --no-deps backend-tests ruff format app tests

clean:
	docker rm -f $(docker ps -a -q) 

purge:
	docker system prune -a --volumes