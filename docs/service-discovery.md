# Service Discovery & Registry Pattern

## Overview

The Omnichannel Publisher uses AWS Cloud Map as a service registry, enabling services to discover and communicate with each other without hardcoded endpoints.

## Architecture

```mermaid
flowchart TB
    subgraph CloudMap["AWS Cloud Map<br/>Namespace: secure-api.local"]
        API_REG["api.secure-api.local"]
        WORKER_REG["worker.secure-api.local"]
        SCHEDULER_REG["scheduler.secure-api.local"]
    end

    subgraph Services["ECS Fargate Services"]
        API["API Service<br/>:8080"]
        WORKER["Worker Service<br/>:8080"]
        SCHEDULER["Scheduler Service<br/>:8080"]
    end

    subgraph DNS["Route 53 Private<br/>Hosted Zone"]
        R53["DNS Resolution"]
    end

    API_REG --> API
    WORKER_REG --> WORKER
    SCHEDULER_REG --> SCHEDULER

    CloudMap --> R53

    style CloudMap fill:#e3f2fd
    style Services fill:#e8f5e9
```

## Service Registration Flow

```mermaid
sequenceDiagram
    participant ECS as ECS Service
    participant Task as Fargate Task
    participant CM as Cloud Map
    participant R53 as Route 53

    ECS->>Task: Start task
    Task->>Task: Health check passes
    Task->>CM: Register instance
    CM->>R53: Create DNS record
    R53-->>CM: Record created
    CM-->>Task: Registration complete

    Note over Task,R53: Task is now discoverable

    Task->>Task: Task stops/fails
    Task->>CM: Deregister instance
    CM->>R53: Remove DNS record
```

## Service Communication Patterns

### Synchronous (Request/Response)

```mermaid
sequenceDiagram
    participant API as API Service
    participant DNS as Cloud Map DNS
    participant Worker as Worker Service

    API->>DNS: Resolve worker.secure-api.local
    DNS-->>API: 10.0.1.45, 10.0.2.67
    API->>Worker: HTTP POST /process
    Worker-->>API: Response
```

### Asynchronous (Event-driven)

```mermaid
flowchart LR
    API["API Service"]
    KINESIS["Kinesis<br/>Stream"]
    WORKER["Worker Service"]

    API -->|"Publish Event"| KINESIS
    KINESIS -->|"Consume Event"| WORKER

    style KINESIS fill:#fff3e0
```

### Scheduled Jobs

```mermaid
flowchart LR
    SCHEDULER["Scheduler<br/>Service"]
    DB[("Database")]
    KINESIS2["Kinesis<br/>Stream"]
    WORKER2["Worker<br/>Service"]

    SCHEDULER -->|"Poll due messages"| DB
    SCHEDULER -->|"Publish events"| KINESIS2
    KINESIS2 -->|"Process"| WORKER2
```

## Services Overview

```mermaid
flowchart TB
    subgraph External["External"]
        USER[("👤 User")]
        ALB["Application<br/>Load Balancer"]
    end

    subgraph Internal["Internal Services"]
        API["API Service<br/>api.secure-api.local<br/>• REST endpoints<br/>• Message scheduling"]
        WORKER["Worker Service<br/>worker.secure-api.local<br/>• Kinesis consumer<br/>• Channel delivery"]
        SCHEDULER["Scheduler Service<br/>scheduler.secure-api.local<br/>• Cron polling<br/>• Due message dispatch"]
    end

    subgraph Data["Data Layer"]
        KINESIS3["Kinesis"]
        RDS[("RDS")]
    end

    USER --> ALB --> API
    API --> KINESIS3
    API --> RDS
    SCHEDULER --> RDS
    SCHEDULER --> KINESIS3
    KINESIS3 --> WORKER
    WORKER --> RDS

    style External fill:#e8f5e9
    style Internal fill:#e3f2fd
    style Data fill:#fff3e0
```

## DNS-based Load Balancing

```mermaid
flowchart TB
    subgraph Client["API Service"]
        REQ["HTTP Request"]
    end

    subgraph DNS2["DNS Query"]
        QUERY["worker.secure-api.local"]
    end

    subgraph Response["DNS Response"]
        IP1["10.0.1.45"]
        IP2["10.0.2.67"]
        IP3["10.0.1.89"]
    end

    subgraph Workers["Worker Tasks"]
        W1["Task 1<br/>10.0.1.45"]
        W2["Task 2<br/>10.0.2.67"]
        W3["Task 3<br/>10.0.1.89"]
    end

    REQ --> QUERY
    QUERY --> Response
    IP1 -.-> W1
    IP2 -.-> W2
    IP3 -.-> W3

    style Response fill:#e8f5e9
```

## Health Checks

```mermaid
flowchart LR
    subgraph Task["Fargate Task"]
        APP["Application"]
        HEALTH["/health"]
        READY["/health/ready"]
    end

    subgraph Checks["Health Checks"]
        ALB_HC["ALB Health Check<br/>/health"]
        CM_HC["Cloud Map Health Check<br/>/health"]
    end

    subgraph Status["Registration Status"]
        HEALTHY["✓ Registered<br/>DNS record active"]
        UNHEALTHY["✗ Deregistered<br/>DNS record removed"]
    end

    ALB_HC --> HEALTH
    CM_HC --> HEALTH
    HEALTH -->|"200 OK"| HEALTHY
    HEALTH -->|"5xx/Timeout"| UNHEALTHY
```

## Service Client Implementation

```mermaid
classDiagram
    class ServiceEndpoints {
        +str api
        +str worker
        +str scheduler
        +int port
        +api_url(path) str
        +worker_url(path) str
    }

    class ServiceClient {
        -ServiceEndpoints endpoints
        -AsyncClient client
        +call_worker(path, data) dict
        +call_api(path, data) dict
        +close()
    }

    ServiceClient --> ServiceEndpoints
```

## Environment Configuration

```mermaid
flowchart LR
    subgraph ECS["ECS Task Definition"]
        ENV["Environment Variables"]
    end

    subgraph Config["Service Configuration"]
        NS["SERVICE_NAMESPACE<br/>secure-api.local"]
        API_HOST["API_SERVICE_HOST<br/>api.secure-api.local"]
        WORKER_HOST["WORKER_SERVICE_HOST<br/>worker.secure-api.local"]
        SCHEDULER_HOST["SCHEDULER_SERVICE_HOST<br/>scheduler.secure-api.local"]
    end

    ECS --> Config
```

## Benefits

```mermaid
mindmap
  root((Service Discovery))
    Dynamic
      No hardcoded IPs
      Auto-registration
      Auto-deregistration
    Scalable
      New tasks register automatically
      Load balancing via DNS
    Resilient
      Failed tasks removed
      Traffic routes to healthy
    Simple
      DNS-based
      No extra infrastructure
      VPC-native
```

## Comparison with Alternatives

| Approach | Pros | Cons |
|----------|------|------|
| **Cloud Map** | AWS-native, auto-registration, DNS-based | AWS-specific |
| Consul | Feature-rich, multi-cloud | Extra infrastructure |
| Eureka | Java ecosystem standard | JVM-centric |
| Kubernetes DNS | K8s-native | Requires K8s |

## References

- [AWS Cloud Map Documentation](https://docs.aws.amazon.com/cloud-map/)
- [ECS Service Discovery](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-discovery.html)
- [Microservices Patterns - Service Discovery](https://microservices.io/patterns/service-registry.html)
