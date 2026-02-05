# Security: Zero Trust & Secure Supply Chain

## Overview

This document outlines the Zero Trust architecture and Secure Supply Chain practices implemented in the Omnichannel Publisher platform.

## Zero Trust Principles

**"Never trust, always verify"** - Every request is authenticated and authorized regardless of network location.

```mermaid
mindmap
  root((Zero Trust))
    Verify Explicitly
      Authenticate all requests
      Authorize based on context
      Multi-factor authentication
    Least Privilege
      Just-in-time access
      Just-enough access
      Role-based permissions
    Assume Breach
      Minimize blast radius
      Segment access
      End-to-end encryption
```

## Network Security Architecture

```mermaid
flowchart TB
    subgraph Internet
        USER[("👤 User")]
    end

    subgraph Edge["Edge Layer"]
        CF["CloudFront<br/>+ Shield"]
        WAF_EDGE["WAF<br/>OWASP Rules<br/>Rate Limiting"]
    end

    subgraph VPC["AWS VPC"]
        subgraph Public["Public Subnet"]
            ALB["Application<br/>Load Balancer"]
            WAF_ALB["WAF<br/>SQL Injection<br/>Bad Inputs"]
        end

        subgraph Private["Private Subnet"]
            ECS["ECS Fargate<br/>Tasks"]
        end

        subgraph Isolated["Isolated Subnet"]
            RDS[("RDS<br/>PostgreSQL")]
        end
    end

    subgraph Security["Security Services"]
        GD["GuardDuty"]
        SH["Security Hub"]
        CT["CloudTrail"]
    end

    USER -->|"TLS 1.3"| CF
    CF --> WAF_EDGE
    WAF_EDGE -->|"TLS 1.3"| ALB
    ALB --> WAF_ALB
    WAF_ALB -->|"TLS 1.3"| ECS
    ECS -->|"TLS"| RDS

    GD -.->|"Monitors"| VPC
    CT -.->|"Audits"| VPC
    SH -.->|"Aggregates"| GD
    SH -.->|"Aggregates"| CT

    style Edge fill:#e8f5e9
    style Public fill:#fff3e0
    style Private fill:#e3f2fd
    style Isolated fill:#fce4ec
```

## Identity & Access Flow

```mermaid
sequenceDiagram
    participant User
    participant CloudFront
    participant WAF
    participant ALB
    participant API as API Service
    participant Cognito
    participant RDS

    User->>CloudFront: Request + JWT
    CloudFront->>WAF: Check rules
    WAF-->>CloudFront: Pass/Block
    CloudFront->>ALB: Forward request
    ALB->>API: Route to service
    
    API->>API: Validate JWT signature
    API->>Cognito: Verify token (cached)
    Cognito-->>API: Token valid + claims
    
    API->>API: Check RBAC permissions
    API->>RDS: Query with IAM auth
    RDS-->>API: Data
    API-->>User: Response
```

## Authentication Providers

```mermaid
flowchart TB
    subgraph Providers["Identity Providers"]
        COGNITO["Cognito<br/>Email/Password"]
        GOOGLE["Google<br/>OAuth 2.0"]
        GITHUB["GitHub<br/>OIDC"]
        LINKEDIN["LinkedIn<br/>OIDC"]
    end

    subgraph Pool["Cognito User Pool"]
        FEDERATE["Federation<br/>Layer"]
        USERS["User<br/>Directory"]
        GROUPS["Groups<br/>admin, community-manager"]
    end

    subgraph Tokens["Token Issuance"]
        JWT["JWT Tokens<br/>• Access Token (1h)<br/>• ID Token (1h)<br/>• Refresh Token (30d)"]
    end

    COGNITO --> FEDERATE
    GOOGLE --> FEDERATE
    GITHUB --> FEDERATE
    LINKEDIN --> FEDERATE
    
    FEDERATE --> USERS
    USERS --> GROUPS
    GROUPS --> JWT

    style COGNITO fill:#ff9800
    style GOOGLE fill:#4285f4
    style GITHUB fill:#333
    style LINKEDIN fill:#0077b5
```

### OAuth Credentials Storage

OAuth client credentials are stored securely in AWS Secrets Manager:

| Provider | Secret Name | Fields |
|----------|-------------|--------|
| Google | `omnichannel/oauth/google` | `client_id`, `client_secret` |
| GitHub | `omnichannel/oauth/github` | `client_id`, `client_secret` |
| LinkedIn | `omnichannel/oauth/linkedin` | `client_id`, `client_secret` |

## Data Protection

```mermaid
flowchart LR
    subgraph Transit["In Transit"]
        TLS["TLS 1.3<br/>Everywhere"]
    end

    subgraph Rest["At Rest"]
        KMS["KMS<br/>Encryption"]
        S3E["S3<br/>SSE-KMS"]
        RDSE["RDS<br/>Encrypted"]
        KINE["Kinesis<br/>Encrypted"]
    end

    subgraph Use["In Use"]
        NOLOG["No PII<br/>in Logs"]
        MASK["Field-level<br/>Encryption"]
    end

    Transit --> Rest --> Use
```

## Micro-segmentation

```mermaid
flowchart TB
    subgraph SG["Security Groups"]
        ALB_SG["ALB SG<br/>Inbound: 443"]
        API_SG["API SG<br/>Inbound: 8080 from ALB"]
        WORKER_SG["Worker SG<br/>Inbound: 8080 from API"]
        DB_SG["DB SG<br/>Inbound: 5432 from API/Worker"]
    end

    ALB_SG -->|"8080"| API_SG
    API_SG -->|"8080"| WORKER_SG
    API_SG -->|"5432"| DB_SG
    WORKER_SG -->|"5432"| DB_SG

    style ALB_SG fill:#e8f5e9
    style API_SG fill:#e3f2fd
    style WORKER_SG fill:#fff3e0
    style DB_SG fill:#fce4ec
```

## Secure Supply Chain

### Build Pipeline Security

```mermaid
flowchart LR
    subgraph Source["Source"]
        GIT["Git<br/>Signed Commits"]
        PR["PR Review<br/>Required"]
    end

    subgraph Scan["Security Scanning"]
        DEP["Dependency<br/>Audit"]
        SAST["Static<br/>Analysis"]
        SECRET["Secret<br/>Scanning"]
    end

    subgraph Build["Container Build"]
        BASE["Minimal<br/>Base Image"]
        NONROOT["Non-root<br/>User"]
        READONLY["Read-only<br/>Filesystem"]
    end

    subgraph Sign["Signing"]
        SIGN["Image<br/>Signing"]
        SBOM["SBOM<br/>Generation"]
    end

    subgraph Deploy["Deployment"]
        VERIFY["Signature<br/>Verification"]
        ECR["ECR<br/>Scanning"]
    end

    Source --> Scan --> Build --> Sign --> Deploy
```

### Container Security Layers

```mermaid
flowchart TB
    subgraph Image["Container Image"]
        DISTROLESS["Distroless Base<br/>(No shell, minimal attack surface)"]
        APP["Application Code"]
        DEPS["Dependencies<br/>(Pinned versions + hashes)"]
    end

    subgraph Runtime["Runtime Security"]
        NONROOT2["Non-root User"]
        READONLY2["Read-only Root FS"]
        NOPRIVESC["No Privilege Escalation"]
        LIMITS["Resource Limits"]
    end

    subgraph Network["Network Security"]
        NOEGRESS["No Internet Egress"]
        VPCE["VPC Endpoints Only"]
        SG2["Security Groups"]
    end

    Image --> Runtime --> Network
```

### CI/CD Security Gates

```mermaid
flowchart LR
    subgraph PR["Pull Request"]
        LINT["Lint"]
        TEST["Unit Tests"]
    end

    subgraph Security["Security Checks"]
        AUDIT["pip-audit<br/>npm audit"]
        BANDIT["Bandit<br/>Semgrep"]
        TRIVY["Trivy<br/>Container Scan"]
        GITLEAKS["Gitleaks<br/>Secret Scan"]
    end

    subgraph Quality["Quality Gates"]
        COV["Coverage<br/>> 80%"]
        SBOM2["SBOM<br/>Generation"]
    end

    subgraph Deploy2["Deploy"]
        SIGN2["Sign Image"]
        PUSH["Push to ECR"]
        DEPLOY["Deploy to ECS"]
    end

    PR --> Security --> Quality --> Deploy2
```

## Threat Detection & Response

```mermaid
flowchart TB
    subgraph Detection["Threat Detection"]
        GD2["GuardDuty<br/>• Malicious IPs<br/>• Unusual API calls<br/>• Container threats"]
        SH2["Security Hub<br/>• Aggregated findings<br/>• Compliance checks"]
        CT2["CloudTrail<br/>• API audit log<br/>• Tamper-proof"]
    end

    subgraph Response["Automated Response"]
        EB["EventBridge<br/>Rule"]
        LAMBDA["Lambda<br/>Function"]
        WAFIP["WAF IP Set<br/>Update"]
    end

    subgraph Alert["Alerting"]
        SLACK["Slack"]
        PD["PagerDuty"]
    end

    GD2 -->|"Finding"| EB
    EB -->|"Severity >= 4"| LAMBDA
    LAMBDA -->|"Block IP"| WAFIP
    LAMBDA -->|"Notify"| Alert

    SH2 -.-> GD2
    CT2 -.-> SH2
```

## Security Checklist

```mermaid
flowchart TB
    subgraph Dev["Development"]
        D1["✓ Signed commits"]
        D2["✓ Branch protection"]
        D3["✓ Pre-commit hooks"]
    end

    subgraph Deps["Dependencies"]
        P1["✓ Lock file with hashes"]
        P2["✓ Vulnerability scanning"]
        P3["✓ SBOM generated"]
    end

    subgraph Container["Container"]
        C1["✓ Distroless base"]
        C2["✓ Non-root user"]
        C3["✓ Image signed"]
    end

    subgraph Infra["Infrastructure"]
        I1["✓ TLS 1.3 everywhere"]
        I2["✓ KMS encryption"]
        I3["✓ VPC endpoints"]
    end

    subgraph Runtime2["Runtime"]
        R1["✓ JWT validation"]
        R2["✓ Rate limiting"]
        R3["✓ GuardDuty enabled"]
    end

    Dev --> Deps --> Container --> Infra --> Runtime2
```

## Dockerfile Security Example

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

## References

- [NIST Zero Trust Architecture (SP 800-207)](https://csrc.nist.gov/publications/detail/sp/800-207/final)
- [SLSA Supply Chain Framework](https://slsa.dev/)
- [OWASP Container Security](https://cheatsheetseries.owasp.org/cheatsheets/Docker_Security_Cheat_Sheet.html)
- [AWS Well-Architected Security Pillar](https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/welcome.html)
