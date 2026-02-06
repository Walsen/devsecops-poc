# List available recipes
default:
    @just --list

# Setup
# Install git hooks
install-hooks:
    @echo "Installing git hooks..."
    @cp scripts/git-hooks/pre-push .git/hooks/pre-push
    @chmod +x .git/hooks/pre-push
    @echo "✓ Git hooks installed"

# Uninstall git hooks
uninstall-hooks:
    @echo "Removing git hooks..."
    @rm -f .git/hooks/pre-push
    @echo "✓ Git hooks removed"

# Run pre-push checks manually
check:
    @./scripts/git-hooks/pre-push

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

# Run linters locally (without Docker)
lint-local:
    @echo "Linting API..."
    uv run --directory api ruff check src/
    @echo "Linting Worker..."
    uv run --directory worker ruff check src/
    @echo "Linting Scheduler..."
    uv run --directory scheduler ruff check src/
    @echo "Linting Infra..."
    uv run --directory infra ruff check stacks/

# Run tests locally (without Docker)
test-local:
    @echo "Testing API..."
    uv run --directory api --extra dev pytest tests/ -v
    @echo "Testing Worker..."
    uv run --directory worker --extra dev pytest tests/ -v

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

# Frontend
# Install frontend dependencies
web-install:
    cd web && npm install

# Start frontend dev server
web-dev:
    cd web && npm run dev

# Build frontend for production
web-build:
    cd web && npm run build

# Preview production build
web-preview:
    cd web && npm run preview

# Lint frontend
web-lint:
    cd web && npm run lint

# Run frontend tests
web-test:
    cd web && npm test

# Run frontend tests in watch mode
web-test-watch:
    cd web && npm run test:watch

# Security Scanning
# Quick security scan (SAST + SCA)
security-scan:
    @echo "🔒 Running security scans..."
    @echo ""
    @echo "=== Semgrep (SAST) ==="
    uv tool run semgrep scan --config p/owasp-top-ten --config p/security-audit api/src/ worker/src/ scheduler/src/ || true
    @echo ""
    @echo "=== Bandit (Python SAST) ==="
    uv tool run bandit -r api/src/ worker/src/ scheduler/src/ -ll -ii || true
    @echo ""
    @echo "=== pip-audit (Python CVEs) ==="
    @for service in api worker scheduler; do \
        echo "Checking $$service..."; \
        uv run --directory $$service pip freeze > /tmp/$$service-reqs.txt 2>/dev/null; \
        uv tool run pip-audit -r /tmp/$$service-reqs.txt 2>/dev/null || true; \
    done
    @echo ""
    @echo "=== Gitleaks (Secrets) ==="
    gitleaks detect --source . --verbose || true
    @echo ""
    @echo "✅ Security scan complete"

# Container security scan with Trivy
trivy-scan:
    @echo "🐳 Scanning containers with Trivy..."
    @for service in api worker scheduler; do \
        echo "=== Building and scanning $$service ==="; \
        docker build -t $$service:scan ./$$service 2>/dev/null; \
        trivy image --severity CRITICAL,HIGH $$service:scan || true; \
    done

# Generate and scan SBOMs
sbom-scan:
    @echo "📦 Generating and scanning SBOMs..."
    @mkdir -p sbom-reports
    @for service in api worker scheduler; do \
        echo "=== $$service SBOM ==="; \
        uv run --directory $$service pip freeze > /tmp/$$service-reqs.txt 2>/dev/null; \
        uv tool run cyclonedx-py requirements \
            --input-file /tmp/$$service-reqs.txt \
            --output-file sbom-reports/$$service-sbom.json \
            --format json 2>/dev/null || true; \
        trivy sbom sbom-reports/$$service-sbom.json --severity CRITICAL,HIGH || true; \
    done
    @echo ""
    @echo "=== Frontend SBOM ==="
    cd web && npx @cyclonedx/cyclonedx-npm --output-file ../sbom-reports/web-sbom.json 2>/dev/null || true
    trivy sbom sbom-reports/web-sbom.json --severity CRITICAL,HIGH || true
    @echo ""
    @echo "✅ SBOMs saved to sbom-reports/"

# IaC security scan with Checkov
iac-scan:
    @echo "🏗️ Scanning infrastructure with Checkov..."
    @echo "=== Synthesizing CDK ==="
    uv run --directory infra cdk synth --quiet 2>/dev/null || true
    @echo ""
    @echo "=== Checkov scan ==="
    uv tool run checkov -d infra/cdk.out --framework cloudformation --soft-fail || true

# DAST scan with Nuclei (requires target URL)
nuclei-scan target:
    @echo "🎯 Running Nuclei scan against {{target}}..."
    nuclei -u {{target}} \
        -t cves/ \
        -t vulnerabilities/ \
        -t exposures/ \
        -t misconfiguration/ \
        -severity critical,high,medium \
        -o nuclei-results.txt || true
    @echo ""
    @echo "✅ Results saved to nuclei-results.txt"

# AWS security scan with Prowler
prowler-scan:
    @echo "☁️ Running Prowler AWS security scan..."
    prowler aws \
        --severity critical high \
        --services ecs rds s3 iam kms secretsmanager cognito waf cloudfront \
        --output-formats json html \
        --output-directory prowler-results || true
    @echo ""
    @echo "✅ Results saved to prowler-results/"

# Full penetration test suite
pentest-full target="http://localhost:8000":
    @echo "🔐 Running full penetration test suite..."
    @echo "Target: {{target}}"
    @echo ""
    just security-scan
    @echo ""
    just trivy-scan
    @echo ""
    just sbom-scan
    @echo ""
    just iac-scan
    @echo ""
    @echo "=== Nuclei DAST Scan ==="
    just nuclei-scan {{target}}
    @echo ""
    @echo "🎉 Full penetration test complete!"
    @echo "Review results in:"
    @echo "  - sbom-reports/"
    @echo "  - nuclei-results.txt"
    @echo "  - prowler-results/ (if AWS scan was run)"

# JWT security test
jwt-test token:
    @echo "🔑 Testing JWT security..."
    jwt_tool {{token}} -M at || true

# Check security headers
headers-check url:
    @echo "📋 Checking security headers for {{url}}..."
    @curl -sI {{url}} | grep -iE "^(content-security-policy|x-frame-options|x-content-type-options|strict-transport-security|permissions-policy|x-xss-protection|referrer-policy):" || echo "Some headers may be missing"

# Install security tools
security-tools-install:
    @echo "🔧 Installing security tools..."
    uv tool install semgrep
    uv tool install bandit
    uv tool install pip-audit
    uv tool install cyclonedx-bom
    uv tool install checkov
    pip install prowler jwt_tool
    @echo ""
    @echo "For additional tools, install manually:"
    @echo "  - Trivy: https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
    @echo "  - Nuclei: go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
    @echo "  - Gitleaks: brew install gitleaks (or from GitHub releases)"
    @echo ""
    @echo "✅ Core security tools installed"
