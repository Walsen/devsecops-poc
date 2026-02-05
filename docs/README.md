# Omnichannel Publisher Platform

## Project Goal

Build a secure, scalable platform for publishing announcements across multiple social media channels. The primary use case is the **AWS Certification Announcer** - a community tool where members can submit their AWS certification achievements, which are then automatically published to community social media accounts (Facebook, Instagram, WhatsApp, LinkedIn).

## Architecture Overview

```mermaid
flowchart TB
    subgraph Users["Users"]
        WEB["🌐 Web App"]
        MOBILE["📱 Mobile"]
    end

    subgraph Edge["Edge Layer"]
        CF["CloudFront"]
        WAF["WAF"]
    end

    subgraph Auth["Authentication"]
        COGNITO["Cognito"]
        GOOGLE["Google"]
        GITHUB["GitHub"]
        LINKEDIN["LinkedIn"]
    end

    subgraph Compute["Compute Layer"]
        ALB["ALB"]
        API["API Service<br/>FastAPI"]
        WORKER["Worker Service<br/>Channel Delivery"]
        SCHEDULER["Scheduler Service<br/>Cron Jobs"]
    end

    subgraph Data["Data Layer"]
        RDS[("PostgreSQL")]
        KINESIS["Kinesis"]
        S3["S3"]
    end

    subgraph Channels["Delivery Channels"]
        FB["Facebook"]
        IG["Instagram"]
        WA["WhatsApp"]
        LI["LinkedIn"]
        EMAIL["Email"]
        SMS["SMS"]
    end

    Users --> Edge
    Edge --> ALB
    ALB --> API
    
    COGNITO --> API
    GOOGLE --> COGNITO
    GITHUB --> COGNITO
    LINKEDIN --> COGNITO
    
    API --> RDS
    API --> KINESIS
    KINESIS --> WORKER
    SCHEDULER --> KINESIS
    SCHEDULER --> RDS
    
    WORKER --> Channels

    style Edge fill:#e8f5e9
    style Auth fill:#e3f2fd
    style Compute fill:#fff3e0
    style Data fill:#fce4ec
    style Channels fill:#f3e5f5
```

## Key Features

- **Multi-channel Publishing**: Facebook, Instagram, WhatsApp, LinkedIn, Email, SMS
- **Social Authentication**: Google, GitHub, LinkedIn, or email/password
- **Scheduled Messages**: Schedule announcements for future delivery
- **Role-based Access**: Admin and Community Manager roles
- **Zero Trust Security**: WAF, encryption, GuardDuty, Security Hub
- **Secure Supply Chain**: Signed containers, SBOM, vulnerability scanning

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React/Next.js (planned) |
| API | FastAPI (Python) |
| Database | PostgreSQL (RDS) |
| Queue | Kinesis Data Streams |
| Auth | Cognito + Social Providers |
| Infrastructure | AWS CDK (Python) |
| Containers | ECS Fargate |
| CI/CD | GitHub Actions |

## Services

### API Service
Handles HTTP requests, authentication, and message scheduling. Implements hexagonal architecture with clean separation of concerns.

### Worker Service
Consumes messages from Kinesis and delivers them to the appropriate channels (Facebook, Instagram, WhatsApp, LinkedIn, Email, SMS).

### Scheduler Service
Polls the database for scheduled messages and publishes them to Kinesis when due.

## Documentation

- [Architecture](architecture.md) - Detailed system architecture and patterns
- [Security](security.md) - Zero Trust and Secure Supply Chain practices
- [Service Discovery](service-discovery.md) - Cloud Map and inter-service communication
- [AI Agents](ai-agents.md) - Using Bedrock Agents for intelligent posting

## Use Cases

- [AWS Certification Announcer](use-cases/aws-certification-announcer.md) - Primary use case

## Getting Started

### Prerequisites

- [devbox](https://www.jetpack.io/devbox/) - Development environment
- [Docker](https://www.docker.com/) - Container runtime
- [just](https://github.com/casey/just) - Task runner

### Local Development

```bash
# Start local services (PostgreSQL, LocalStack)
just up

# Run database migrations
just migrate

# Start API in development mode
just dev-api

# Run tests
just test
```

### Deployment

```bash
# Deploy infrastructure
cd infra
uv run cdk deploy --all
```

## Project Structure

```
.
├── api/                    # API service (FastAPI)
│   ├── src/
│   │   ├── domain/         # Business entities
│   │   ├── application/    # Use cases and ports
│   │   ├── infrastructure/ # Adapters (DB, Kinesis)
│   │   └── presentation/   # HTTP layer
│   └── tests/
├── worker/                 # Worker service (Kinesis consumer)
│   └── src/
│       └── channels/       # Channel gateways
├── scheduler/              # Scheduler service (cron)
├── infra/                  # CDK infrastructure
│   └── stacks/
├── docs/                   # Documentation
└── .github/                # CI/CD workflows
```

## License

MIT
