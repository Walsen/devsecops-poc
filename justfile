# List available recipes
default:
    @just --list

# Development
# Start development environment and tail logs
dev: up logs

# Start all services
up:
    docker compose up -d

# Stop all services
down:
    docker compose down

# Tail logs from all services
logs:
    docker compose logs -f

# Rebuild all containers
build:
    docker compose build --no-cache

# Stop services and remove volumes
clean:
    docker compose down -v
    docker system prune -f

# Database
# Open PostgreSQL shell
db-shell:
    docker compose exec postgres psql -U dbadmin -d omnichannel

# Run database migrations
db-migrate:
    docker compose exec api alembic upgrade head

# Create a new migration
db-revision message:
    docker compose exec api alembic revision --autogenerate -m "{{message}}"

# Show migration history
db-history:
    docker compose exec api alembic history

# Rollback last migration
db-rollback:
    docker compose exec api alembic downgrade -1

# Service shells
# Open shell in API container
api-shell:
    docker compose exec api bash

# Open shell in Worker container
worker-shell:
    docker compose exec worker bash

# Open shell in Scheduler container
scheduler-shell:
    docker compose exec scheduler bash

# Testing
# Run all tests
test:
    docker compose exec api pytest -v

# Run API tests
test-api:
    docker compose exec api pytest -v tests/

# Run Worker tests
test-worker:
    docker compose exec worker pytest -v tests/

# Run tests with coverage
test-cov:
    docker compose exec api pytest --cov=src --cov-report=html --cov-report=term

# Run specific test file
test-file file:
    docker compose exec api pytest -v {{file}}

# Run tests matching pattern
test-match pattern:
    docker compose exec api pytest -v -k "{{pattern}}"

# Linting
# Run linters
lint:
    docker compose exec api ruff check src/
    docker compose exec api mypy src/

# LocalStack
# View LocalStack logs
localstack-logs:
    docker compose logs localstack

# List Kinesis streams
kinesis-list:
    aws --endpoint-url=http://localhost:4566 kinesis list-streams

# CDK
# Synthesize CDK stacks
cdk-synth:
    cd infra && cdk synth

# Deploy CDK stacks
cdk-deploy:
    cd infra && cdk deploy --all

# Destroy CDK stacks
cdk-destroy:
    cd infra && cdk destroy --all
