.PHONY: help test test-verbose test-parallel test-keepdb test-models test-views test-api test-integration run migrate makemigrations shell superuser collectstatic install sync clean docker-up docker-down docker-logs docker-migrate dump-data run-black start

help:
	@echo "Available commands:"
	@echo "  make run              - Run Django development server"
	@echo "  make test             - Run all tests"
	@echo "  make test-verbose     - Run tests with verbose output"
	@echo "  make test-parallel    - Run tests in parallel"
	@echo "  make test-keepdb      - Run tests keeping the test database"
	@echo "  make test-models      - Run model tests only"
	@echo "  make test-views       - Run view tests only"
	@echo "  make test-api         - Run API tests only"
	@echo "  make test-integration - Run integration tests only"
	@echo "  make migrate          - Run database migrations"
	@echo "  make makemigrations   - Create new migrations"
	@echo "  make shell            - Open Django shell"
	@echo "  make superuser        - Create a superuser"
	@echo "  make collectstatic    - Collect static files"
	@echo "  make install          - Install dependencies with uv"
	@echo "  make sync             - Sync dependencies with uv"
	@echo "  make clean            - Remove Python cache files"
	@echo "  make docker-up        - Start all Docker services"
	@echo "  make docker-down      - Stop all Docker services"
	@echo "  make docker-logs      - View Docker logs"
	@echo "  make docker-migrate   - Run migrations in Docker container"
	@echo "  make dump-data        - Dump content from local database to json file"
	@echo "  make run-black        - Run black across repo"
	@echo "  make start            - Run game initializer"

# Run development server
run:
	uv run manage.py runserver

# Test commands
test:
	uv run manage.py test quiz

test-verbose:
	uv run manage.py test quiz --verbosity=2

test-parallel:
	uv run manage.py test quiz --parallel

test-keepdb:
	uv run manage.py test quiz --keepdb

test-models:
	uv run manage.py test quiz.tests.test_models

test-views:
	uv run manage.py test quiz.tests.test_views

test-api:
	uv run manage.py test quiz.tests.test_api_views

test-integration:
	uv run manage.py test quiz.tests.test_integration

# Database commands
migrate:
	uv run manage.py migrate

makemigrations:
	uv run manage.py makemigrations

# Django utilities
shell:
	uv run manage.py shell

superuser:
	uv run manage.py createsuperuser

collectstatic:
	uv run manage.py collectstatic --noinput

# Dependency management
install:
	uv sync

sync:
	uv sync

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name ".DS_Store" -delete

# Docker commands
docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f web

docker-migrate:
	docker-compose exec web uv run manage.py migrate

# Dump content from database to json file
dump-data:
	uv run manage.py dumpdata --indent 2 > db_initial_data.json

# Run black
run-black:
	uv run black .

# Start a new game
start:
	uv run init_trivia.py