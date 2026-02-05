# Service Discovery & Registry Pattern

## Overview

The Omnichannel Publisher uses AWS Cloud Map as a service registry, enabling services to discover and communicate with each other without hardcoded endpoints.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AWS Cloud Map                             │
│              Namespace: secure-api.local                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐ │
│  │   API Service   │  │  Worker Service │  │  Scheduler  │ │
│  │                 │  │                 │  │   Service   │ │
│  │ api.secure-api  │  │ worker.secure-  │  │ scheduler.  │ │
│  │    .local       │  │   api.local     │  │ secure-api  │ │
│  │                 │  │                 │  │   .local    │ │
│  └────────┬────────┘  └────────┬────────┘  └──────┬──────┘ │
│           │                    │                   │        │
│           └────────────────────┼───────────────────┘        │
│                                │                            │
│                    ┌───────────▼───────────┐                │
│                    │    Route 53 Private   │                │
│                    │     Hosted Zone       │                │
│                    └───────────────────────┘                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Services

| Service | DNS Name | Purpose |
|---------|----------|---------|
| API | `api.secure-api.local` | Sync REST API, handles user requests |
| Worker | `worker.secure-api.local` | Async Kinesis consumers, channel delivery |
| Scheduler | `scheduler.secure-api.local` | Cron jobs, scheduled message dispatch |

## How It Works

### 1. Service Registration (Automatic)

When an ECS task starts, it automatically registers with Cloud Map:

```
Task starts → Health check passes → Registered in Cloud Map → DNS record created
```

When a task stops or fails health checks:

```
Task stops → Deregistered from Cloud Map → DNS record removed
```

### 2. Service Discovery (DNS-based)

Services discover each other via DNS queries:

```python
# From API service, call worker service
import httpx

async def notify_worker(message_id: str):
    # DNS resolves to healthy task IPs
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://worker.secure-api.local:8080/process",
            json={"message_id": message_id}
        )
    return response.json()
```

### 3. Load Balancing

Cloud Map returns multiple IPs when multiple tasks are running:

```bash
# DNS query returns all healthy instances
$ dig worker.secure-api.local

;; ANSWER SECTION:
worker.secure-api.local. 10 IN A 10.0.1.45
worker.secure-api.local. 10 IN A 10.0.2.67
```

Client-side load balancing happens automatically via DNS round-robin.

## Service Communication Patterns

### Sync (Request/Response)

```
┌─────────┐         ┌─────────┐
│   API   │──HTTP──▶│ Worker  │
│ Service │◀──────── │ Service │
└─────────┘         └─────────┘

Use case: Health checks, status queries
```

### Async (Event-driven)

```
┌─────────┐         ┌─────────┐         ┌─────────┐
│   API   │──────▶  │ Kinesis │  ──────▶│ Worker  │
│ Service │         │ Stream  │         │ Service │
└─────────┘         └─────────┘         └─────────┘

Use case: Message delivery, heavy processing
```

### Scheduled

```
┌───────────┐         ┌─────────┐         ┌─────────┐
│ Scheduler │──────▶  │ Kinesis │  ──────▶│ Worker  │
│  Service  │         │ Stream  │         │ Service │
└───────────┘         └─────────┘         └─────────┘

Use case: Scheduled posts, batch processing
```

## Configuration

### Environment Variables

Each service receives discovery configuration:

```python
# Injected by ECS task definition
SERVICE_NAMESPACE = "secure-api.local"
API_SERVICE_HOST = "api.secure-api.local"
WORKER_SERVICE_HOST = "worker.secure-api.local"
SCHEDULER_SERVICE_HOST = "scheduler.secure-api.local"
```

### Service Client

```python
# infrastructure/discovery/service_client.py
from dataclasses import dataclass
import httpx
import os

@dataclass
class ServiceEndpoints:
    api: str = os.getenv("API_SERVICE_HOST", "api.secure-api.local")
    worker: str = os.getenv("WORKER_SERVICE_HOST", "worker.secure-api.local")
    scheduler: str = os.getenv("SCHEDULER_SERVICE_HOST", "scheduler.secure-api.local")
    port: int = 8080
    
    def api_url(self, path: str) -> str:
        return f"http://{self.api}:{self.port}{path}"
    
    def worker_url(self, path: str) -> str:
        return f"http://{self.worker}:{self.port}{path}"


class ServiceClient:
    """HTTP client for inter-service communication."""
    
    def __init__(self, endpoints: ServiceEndpoints | None = None):
        self.endpoints = endpoints or ServiceEndpoints()
        self._client = httpx.AsyncClient(timeout=30.0)
    
    async def call_worker(self, path: str, data: dict) -> dict:
        response = await self._client.post(
            self.endpoints.worker_url(path),
            json=data,
        )
        response.raise_for_status()
        return response.json()
    
    async def close(self):
        await self._client.aclose()
```

## Health Checks

Cloud Map uses health checks to determine service availability:

```python
# presentation/api/health.py
from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
async def health_check():
    """Health check endpoint for Cloud Map."""
    return {"status": "healthy"}

@router.get("/health/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
    kinesis: KinesisClient = Depends(get_kinesis),
):
    """Readiness check - verifies dependencies."""
    checks = {
        "database": await check_db(db),
        "kinesis": await check_kinesis(kinesis),
    }
    
    all_healthy = all(checks.values())
    return {
        "status": "ready" if all_healthy else "not_ready",
        "checks": checks,
    }
```

## Benefits

| Benefit | Description |
|---------|-------------|
| No hardcoded IPs | Services discover each other dynamically |
| Auto-scaling friendly | New tasks register automatically |
| Fault tolerant | Failed tasks deregister, traffic routes to healthy ones |
| Zero config deploys | No need to update configs when scaling |
| VPC-native | Private DNS, no public exposure |

## Comparison with Alternatives

| Approach | Pros | Cons |
|----------|------|------|
| **Cloud Map (current)** | AWS-native, auto-registration, DNS-based | AWS-specific |
| Consul | Feature-rich, multi-cloud | Extra infrastructure to manage |
| Eureka | Java ecosystem standard | JVM-centric |
| Kubernetes DNS | K8s-native | Requires K8s |

## References

- [AWS Cloud Map Documentation](https://docs.aws.amazon.com/cloud-map/)
- [ECS Service Discovery](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-discovery.html)
- [Microservices Patterns - Service Discovery](https://microservices.io/patterns/service-registry.html)
