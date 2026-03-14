.PHONY: dev dev-backend dev-frontend test test-backend test-frontend lint lint-backend lint-frontend build clean

# Development
dev: dev-backend dev-frontend

dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd frontend && dx serve

# Testing
test: test-backend test-frontend

test-backend:
	cd backend && pytest -v

test-frontend:
	cd frontend && cargo test

test-e2e:
	npx playwright test

# Type checking (Deep Static Test)
typecheck: typecheck-backend typecheck-frontend

typecheck-backend:
	cd backend && mypy --strict app/

typecheck-frontend:
	cd frontend && cargo clippy -- -D warnings

# Linting (Check Syntax)
lint: lint-backend lint-frontend

lint-backend:
	cd backend && ruff check app/ && ruff format --check app/

lint-frontend:
	cd frontend && cargo fmt --check

# Format
format: format-backend format-frontend

format-backend:
	cd backend && ruff format app/

format-frontend:
	cd frontend && cargo fmt

# Build
build: build-backend build-frontend

build-backend:
	cd backend && pip install -e ".[dev]"

build-frontend:
	cd frontend && dx build --release

# Clean
clean:
	rm -rf backend/__pycache__ backend/.pytest_cache backend/.mypy_cache
	rm -rf frontend/target/debug frontend/dist
