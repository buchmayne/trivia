.PHONY: help test test-verbose test-parallel test-keepdb test-models test-views test-api test-integration run migrate makemigrations shell superuser collectstatic install sync clean docker-up docker-down docker-logs docker-migrate dump-data black start preprod e2e e2e-ui e2e-headed e2e-debug e2e-report e2e-install e2e-qa e2e-diagnose e2e-robust

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
	@echo "  make black            - Run black across repo"
	@echo "  make start            - Run game initializer"
	@echo "  make preprod          - Run all preflight steps before pushing to production (linting, tests, and database dump)"
	@echo ""
	@echo "E2E Testing (Playwright):"
	@echo "  make e2e-install      - Install Playwright and browsers"
	@echo "  make e2e              - Run all E2E tests (desktop Chrome)"
	@echo "  make e2e-ui           - Run E2E tests in interactive UI mode"
	@echo "  make e2e-headed       - Run E2E tests with visible browser"
	@echo "  make e2e-debug        - Run E2E tests in debug/step-through mode"
	@echo "  make e2e-qa           - Visual QA: full game at human speed with video"
	@echo "  make e2e-robust       - Robust QA: defensive testing with retries"
	@echo "  make e2e-diagnose     - Diagnostic test with screenshots and logging"
	@echo "  make e2e-report       - View the last test report"
	@echo ""
	@echo "  Run specific test: make e2e-headed TEST=host-flow"

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
	uv run manage.py dumpdata --exclude contenttypes --exclude auth.permission --exclude admin.logentry --exclude sessions --natural-foreign --natural-primary --indent 2 > db_initial_data.json

# Run black
black:
	uv run black .

# Start a new game
start:
	uv run init_trivia.py

# E2E Testing with Playwright
# Use TEST= to run specific test file, e.g.: make e2e-headed TEST=host-flow
TEST ?=

e2e-install:
	npm install
	npx playwright install chromium webkit

e2e:
ifdef TEST
	cd e2e && npx playwright test $(TEST) --project=chromium
else
	cd e2e && npx playwright test --project=chromium
endif

e2e-ui:
ifdef TEST
	cd e2e && npx playwright test $(TEST) --ui
else
	cd e2e && npx playwright test --ui
endif

e2e-headed:
ifdef TEST
	cd e2e && npx playwright test $(TEST) --headed --project=chromium
else
	cd e2e && npx playwright test --headed --project=chromium
endif

e2e-debug:
ifdef TEST
	cd e2e && npx playwright test $(TEST) --debug --project=chromium
else
	cd e2e && npx playwright test --debug --project=chromium
endif

# Visual QA test - runs full game at human-observable speed with video recording
e2e-qa:
	cd e2e && npx playwright test qa-visual.spec.ts --headed --project=qa-visual

# Diagnostic test - captures screenshots and logs element state to identify hang points
e2e-diagnose:
	cd e2e && npx playwright test qa-diagnostic.spec.ts --headed --project=chromium

# Robust QA test - defensive testing with retries, stability checks, and comprehensive diagnostics
e2e-robust:
	cd e2e && npx playwright test qa-robust.spec.ts --headed --project=qa-robust

e2e-report:
	cd e2e && npx playwright show-report

# Run all preflight steps before pushing to prod
preprod:
	uv run manage.py dumpdata --exclude contenttypes --exclude auth.permission --exclude admin.logentry --exclude sessions --natural-foreign --natural-primary --indent 2 > db_initial_data.json
	uv run black .
	uv run manage.py test quiz
