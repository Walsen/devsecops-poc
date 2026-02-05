# Security: Zero Trust & Secure Supply Chain

## Overview

This document outlines the Zero Trust architecture and Secure Supply Chain practices implemented in the Omnichannel Publisher platform.

## Zero Trust Principles

**"Never trust, always verify"** - Every request is authenticated and authorized regardless of network location.

### Core Tenets

1. **Verify explicitly** - Always authenticate and authorize based on all available data points
2. **Use least privilege access** - Limit user/service access with just-in-time and just-enough-access (JIT/JEA)
3. **Assume breach** - Minimize blast radius, segment access, verify end-to-end encryption

## Zero Trust Implementation

### Network Layer

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└─────────────────────────┬───────────────────────────────────┘
                          │ TLS 1.3
┌─────────────────────────▼───────────────────────────────────┐
│  CloudFront + WAF (Edge)                                    │
│  - DDoS protection (Shield)                                 │
│  - OWASP rules                                              │
│  - Rate limiting                                            │
│  - IP blocklist (auto-updated by GuardDuty)                │
└─────────────────────────┬───────────────────────────────────┘
                          │ TLS 1.3
┌─────────────────────────▼───────────────────────────────────┐
│  ALB + WAF (Regional)                                       │
│  - SQL injection protection                                 │
│  - Request validation                                       │
└─────────────────────────┬───────────────────────────────────┘
                          │ TLS 1.3 (internal)
┌─────────────────────────▼───────────────────────────────────┐
│  Private Subnets (ECS Fargate)                             │
│  - No public IPs                                            │
│  - Security groups (micro-segmentation)                     │
│  - VPC endpoints (no internet for AWS services)            │
└─────────────────────────────────────────────────────────────┘
```

### Identity & Access

| Component | Implementation |
|-----------|----------------|
| User Authentication | OAuth 2.0 / OIDC (Cognito or external IdP) |
| Service-to-Service | IAM roles, short-lived credentials |
| API Authorization | JWT validation + RBAC/ABAC |
| Secrets | AWS Secrets Manager, rotated automatically |
| Database | IAM authentication, no static passwords |

### Application Security

```python
# Middleware chain for Zero Trust
app = FastAPI()

# 1. Request ID for tracing
app.add_middleware(RequestIdMiddleware)

# 2. Verify JWT on every request
app.add_middleware(
    JWTAuthMiddleware,
    jwks_url=settings.JWKS_URL,
    audience=settings.API_AUDIENCE,
)

# 3. Rate limiting per identity
app.add_middleware(
    RateLimitMiddleware,
    key_func=lambda r: r.state.user_id,
    limit="100/minute",
)

# 4. Input validation (Pydantic)
# 5. Output sanitization
# 6. Audit logging
```

### Data Protection

| Data State | Protection |
|------------|------------|
| In Transit | TLS 1.3 everywhere (CloudFront → ALB → ECS → RDS) |
| At Rest | KMS encryption (RDS, S3, Kinesis) |
| In Use | No sensitive data in logs, field-level encryption for PII |

### Micro-segmentation

```python
# Security group rules (CDK)
# Each component only talks to what it needs

# ALB → ECS Tasks (port 8080 only)
task_sg.add_ingress_rule(alb_sg, Port.tcp(8080))

# ECS Tasks → RDS (port 5432 only)
db_sg.add_ingress_rule(task_sg, Port.tcp(5432))

# ECS Tasks → VPC Endpoints only (no internet)
# Outbound restricted to AWS services via endpoints
```

## Secure Supply Chain

### Container Security

```
┌─────────────────────────────────────────────────────────────┐
│                    Build Pipeline                            │
├─────────────────────────────────────────────────────────────┤
│  1. Source Code                                             │
│     └── Git signed commits                                  │
│     └── Branch protection rules                             │
│     └── PR reviews required                                 │
│                                                             │
│  2. Dependency Scanning                                     │
│     └── pip-audit / safety (Python)                        │
│     └── npm audit (Node.js)                                │
│     └── SBOM generation (CycloneDX)                        │
│                                                             │
│  3. Static Analysis                                         │
│     └── Bandit (Python security)                           │
│     └── Semgrep (custom rules)                             │
│     └── Trivy (container scanning)                         │
│                                                             │
│  4. Container Build                                         │
│     └── Distroless/minimal base images                     │
│     └── Non-root user                                       │
│     └── Read-only filesystem                               │
│     └── No shell in production image                       │
│                                                             │
│  5. Image Signing                                           │
│     └── Sigstore/cosign                                    │
│     └── ECR image scanning                                 │
│                                                             │
│  6. Deployment                                              │
│     └── Image signature verification                       │
│     └── Immutable tags                                     │
└─────────────────────────────────────────────────────────────┘
```

### Dockerfile Best Practices

```dockerfile
# Use specific digest, not :latest
FROM python:3.12-slim@sha256:abc123... AS builder

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production image - distroless
FROM gcr.io/distroless/python3-debian12

WORKDIR /app

# Copy only what's needed
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /app .

# Non-root user (distroless default)
USER nonroot

# Read-only filesystem compatible
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["python", "-m", "uvicorn", "main:app"]
```

### Dependency Management

```toml
# pyproject.toml - Pin exact versions with hashes
[tool.uv]
resolution = "locked"

[project]
dependencies = [
    "fastapi==0.109.0",
    "sqlalchemy==2.0.25",
    "pydantic==2.5.3",
]

# uv.lock contains hashes for integrity verification
```

### CI/CD Security Gates

```yaml
# .github/workflows/security.yml
name: Security Checks

on: [push, pull_request]

jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      # Dependency vulnerabilities
      - name: Audit dependencies
        run: |
          pip install pip-audit
          pip-audit -r requirements.txt --strict
      
      # Static security analysis
      - name: Run Bandit
        run: bandit -r src/ -ll
      
      # Container scanning
      - name: Trivy scan
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'
      
      # SBOM generation
      - name: Generate SBOM
        run: |
          pip install cyclonedx-bom
          cyclonedx-py -o sbom.json
      
      # Secret scanning
      - name: Gitleaks
        uses: gitleaks/gitleaks-action@v2
```

### Runtime Security

| Control | Implementation |
|---------|----------------|
| Container Runtime | Fargate (no host access, AWS-managed) |
| Read-only Root FS | `readonlyRootFilesystem: true` in task def |
| No Privilege Escalation | `allowPrivilegeEscalation: false` |
| Resource Limits | CPU/memory limits prevent DoS |
| Network Policy | Security groups, no internet egress |
| Secrets Injection | Secrets Manager → ECS secrets (not env vars) |

### Monitoring & Response

```
┌─────────────────────────────────────────────────────────────┐
│                  Threat Detection                            │
├─────────────────────────────────────────────────────────────┤
│  GuardDuty                                                  │
│  └── Malicious IP detection                                │
│  └── Unusual API calls                                     │
│  └── Container runtime threats                             │
│                                                             │
│  Security Hub                                               │
│  └── Aggregated findings                                   │
│  └── Compliance checks (CIS, PCI-DSS)                     │
│                                                             │
│  CloudTrail                                                 │
│  └── API audit log                                         │
│  └── Tamper-proof (S3 + integrity validation)             │
│                                                             │
│  Application Logs                                           │
│  └── Structured JSON logging                               │
│  └── No PII in logs                                        │
│  └── Request tracing (correlation IDs)                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Automated Response                          │
├─────────────────────────────────────────────────────────────┤
│  EventBridge Rule                                           │
│  └── GuardDuty finding (severity >= 4)                    │
│                                                             │
│  Lambda Function                                            │
│  └── Extract attacker IP                                   │
│  └── Update WAF IP blocklist                              │
│  └── Alert to Slack/PagerDuty                             │
└─────────────────────────────────────────────────────────────┘
```

## Security Checklist

### Development
- [ ] Signed commits enabled
- [ ] Branch protection rules configured
- [ ] Pre-commit hooks (secrets, linting)
- [ ] IDE security plugins installed

### Dependencies
- [ ] Lock file with hashes (uv.lock)
- [ ] Automated vulnerability scanning
- [ ] SBOM generated and stored
- [ ] No unnecessary dependencies

### Container
- [ ] Minimal base image (distroless)
- [ ] Non-root user
- [ ] No secrets in image
- [ ] Image signed and verified
- [ ] ECR scanning enabled

### Infrastructure
- [ ] TLS 1.3 everywhere
- [ ] KMS encryption at rest
- [ ] VPC endpoints (no public internet)
- [ ] Security groups (least privilege)
- [ ] WAF rules enabled

### Runtime
- [ ] JWT validation on all endpoints
- [ ] Rate limiting enabled
- [ ] Audit logging configured
- [ ] GuardDuty enabled
- [ ] Automated threat response

## References

- [NIST Zero Trust Architecture (SP 800-207)](https://csrc.nist.gov/publications/detail/sp/800-207/final)
- [SLSA Supply Chain Framework](https://slsa.dev/)
- [OWASP Container Security](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [AWS Well-Architected Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html)
