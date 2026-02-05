# Architecture: Hexagonal (Ports & Adapters)

## Overview

The Omnichannel Publisher follows Hexagonal Architecture (also known as Ports & Adapters), which isolates the core business logic from external concerns like databases, APIs, and message queues.

## Hexagonal Architecture Diagram

```mermaid
graph TB
    subgraph Driving["Driving Side (Primary Adapters)"]
        REST["FastAPI REST<br/>Controller"]
        KINESIS_IN["Kinesis<br/>Consumer"]
    end

    subgraph Ports_In["Inbound Ports (Use Cases)"]
        SCHEDULE["ScheduleMessage<br/>UseCase"]
        GET["GetMessage<br/>UseCase"]
        PROCESS["ProcessMessage<br/>UseCase"]
    end

    subgraph Core["Domain Core"]
        ENTITIES["Entities<br/>Message, ChannelDelivery"]
        VO["Value Objects<br/>ChannelType, MessageContent"]
        SERVICES["Domain Services"]
    end

    subgraph Ports_Out["Outbound Ports"]
        REPO["MessageRepository"]
        EVENTS["EventPublisher"]
        GATEWAY["ChannelGateway"]
        UOW["UnitOfWork"]
    end

    subgraph Driven["Driven Side (Secondary Adapters)"]
        POSTGRES["PostgreSQL<br/>Repository"]
        KINESIS_OUT["Kinesis<br/>Publisher"]
        WHATSAPP["WhatsApp<br/>Gateway"]
        FACEBOOK["Facebook<br/>Gateway"]
        INSTAGRAM["Instagram<br/>Gateway"]
        EMAIL["SES Email<br/>Gateway"]
        SMS["SNS SMS<br/>Gateway"]
    end

    REST --> SCHEDULE
    REST --> GET
    KINESIS_IN --> PROCESS

    SCHEDULE --> Core
    GET --> Core
    PROCESS --> Core

    Core --> REPO
    Core --> EVENTS
    Core --> GATEWAY
    Core --> UOW

    REPO -.-> POSTGRES
    EVENTS -.-> KINESIS_OUT
    GATEWAY -.-> WHATSAPP
    GATEWAY -.-> FACEBOOK
    GATEWAY -.-> INSTAGRAM
    GATEWAY -.-> EMAIL
    GATEWAY -.-> SMS
    UOW -.-> POSTGRES

    style Core fill:#e1f5fe
    style Ports_In fill:#fff3e0
    style Ports_Out fill:#fff3e0
    style Driving fill:#e8f5e9
    style Driven fill:#fce4ec
```

## Layer Responsibilities

### Domain Core (Center)
The heart of the application containing pure business logic with zero external dependencies.

```mermaid
classDiagram
    class Message {
        +UUID id
        +MessageContent content
        +List~ChannelType~ channels
        +datetime scheduled_at
        +MessageStatus status
        +schedule()
        +mark_processing()
        +mark_channel_delivered()
        +mark_channel_failed()
    }

    class MessageContent {
        +str text
        +str media_url
    }

    class ChannelType {
        <<enumeration>>
        WHATSAPP
        FACEBOOK
        INSTAGRAM
        EMAIL
        SMS
    }

    class MessageStatus {
        <<enumeration>>
        DRAFT
        SCHEDULED
        PROCESSING
        DELIVERED
        FAILED
    }

    Message --> MessageContent
    Message --> ChannelType
    Message --> MessageStatus
```

### Inbound Ports (Use Cases)
Abstract interfaces defining what the application can do.

```mermaid
classDiagram
    class ScheduleMessageUseCase {
        <<interface>>
        +execute(dto: CreateMessageDTO) UUID
    }

    class GetMessageUseCase {
        <<interface>>
        +execute(message_id: UUID) MessageResponseDTO
    }

    class ScheduleMessageService {
        -MessageRepository repository
        -EventPublisher publisher
        -UnitOfWork uow
        +execute(dto: CreateMessageDTO) UUID
    }

    class GetMessageService {
        -MessageRepository repository
        +execute(message_id: UUID) MessageResponseDTO
    }

    ScheduleMessageUseCase <|.. ScheduleMessageService
    GetMessageUseCase <|.. GetMessageService
```

### Outbound Ports
Abstract interfaces for external dependencies.

```mermaid
classDiagram
    class MessageRepository {
        <<interface>>
        +save(message: Message)
        +get_by_id(id: UUID) Message
        +get_scheduled_before(before: datetime) List~Message~
    }

    class EventPublisher {
        <<interface>>
        +publish(event_type: str, payload: dict)
    }

    class ChannelGateway {
        <<interface>>
        +send(recipient: str, content: str, media_url: str) DeliveryResult
    }

    class UnitOfWork {
        <<interface>>
        +commit()
        +rollback()
    }
```

### Adapters
Concrete implementations of ports.

```mermaid
classDiagram
    class MessageRepository {
        <<interface>>
    }

    class PostgresMessageRepository {
        -AsyncSession session
        +save(message: Message)
        +get_by_id(id: UUID) Message
    }

    class EventPublisher {
        <<interface>>
    }

    class KinesisEventPublisher {
        -str stream_name
        -str region
        +publish(event_type: str, payload: dict)
    }

    class ChannelGateway {
        <<interface>>
    }

    class WhatsAppGateway {
        -str access_token
        -str phone_number_id
        +send(recipient: str, content: str) DeliveryResult
    }

    class FacebookGateway {
        -str access_token
        -str page_id
        +send(recipient: str, content: str) DeliveryResult
    }

    MessageRepository <|.. PostgresMessageRepository
    EventPublisher <|.. KinesisEventPublisher
    ChannelGateway <|.. WhatsAppGateway
    ChannelGateway <|.. FacebookGateway
```

## Folder Structure

```
api/src/
├── domain/                          # Domain Core
│   ├── entities/
│   │   └── message.py               # Message aggregate root
│   └── value_objects/
│       ├── channel_type.py          # ChannelType enum
│       └── content.py               # MessageContent value object
│
├── application/                     # Application Layer
│   ├── ports/
│   │   ├── inbound/                 # Use case interfaces
│   │   │   ├── schedule_message.py
│   │   │   └── get_message.py
│   │   └── outbound/                # Repository/service interfaces
│   │       ├── message_repository.py
│   │       ├── event_publisher.py
│   │       └── unit_of_work.py
│   ├── services/                    # Use case implementations
│   │   ├── schedule_message_service.py
│   │   └── get_message_service.py
│   └── dtos/                        # Data transfer objects
│       └── message_dto.py
│
├── infrastructure/                  # Infrastructure Layer
│   ├── adapters/
│   │   ├── persistence/             # Database adapters
│   │   │   ├── postgres_message_repository.py
│   │   │   └── sqlalchemy_unit_of_work.py
│   │   └── messaging/               # Message queue adapters
│   │       └── kinesis_event_publisher.py
│   └── persistence/
│       ├── database.py              # Database connection
│       └── models.py                # SQLAlchemy models
│
└── presentation/                    # Presentation Layer
    └── api/
        ├── dependencies.py          # Dependency injection
        └── v1/
            ├── health.py
            └── messages.py          # REST endpoints
```

## Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI as FastAPI Controller
    participant UseCase as ScheduleMessageService
    participant Domain as Message Entity
    participant Repo as PostgresRepository
    participant Publisher as KinesisPublisher
    participant Worker as Worker Service

    Client->>FastAPI: POST /api/v1/messages
    FastAPI->>UseCase: execute(CreateMessageDTO)
    UseCase->>Domain: Message.create()
    Domain-->>UseCase: message
    UseCase->>Domain: message.schedule()
    UseCase->>Repo: save(message)
    Repo-->>UseCase: ok
    UseCase->>Publisher: publish("message.scheduled", payload)
    Publisher-->>UseCase: ok
    UseCase-->>FastAPI: message_id
    FastAPI-->>Client: {"id": "...", "status": "scheduled"}

    Note over Publisher,Worker: Async Processing
    Publisher->>Worker: Kinesis Event
    Worker->>Worker: Deliver to channels
```

## Benefits of Hexagonal Architecture

| Benefit | Description |
|---------|-------------|
| **Testability** | Domain and use cases can be tested without infrastructure |
| **Flexibility** | Swap adapters without changing business logic |
| **Maintainability** | Clear boundaries make code easier to understand |
| **Independence** | Domain doesn't depend on frameworks or databases |
| **Parallel Development** | Teams can work on different adapters independently |

## Dependency Rule

```mermaid
graph LR
    A[Presentation] --> B[Application]
    B --> C[Domain]
    D[Infrastructure] --> B

    style C fill:#e1f5fe
    style B fill:#fff3e0
```

Dependencies always point inward:
- **Presentation** depends on **Application**
- **Application** depends on **Domain**
- **Infrastructure** depends on **Application** (implements ports)
- **Domain** depends on nothing

## Testing Strategy

```mermaid
graph TB
    subgraph Unit["Unit Tests"]
        DOMAIN_TEST["Domain Tests<br/>(No mocks needed)"]
        SERVICE_TEST["Service Tests<br/>(Mock ports)"]
    end

    subgraph Integration["Integration Tests"]
        REPO_TEST["Repository Tests<br/>(Real DB)"]
        ADAPTER_TEST["Adapter Tests<br/>(Real services)"]
    end

    subgraph E2E["End-to-End Tests"]
        API_TEST["API Tests<br/>(Full stack)"]
    end

    DOMAIN_TEST --> SERVICE_TEST
    SERVICE_TEST --> REPO_TEST
    REPO_TEST --> API_TEST
```

| Layer | Test Type | Dependencies |
|-------|-----------|--------------|
| Domain | Unit | None |
| Services | Unit | Mocked ports |
| Adapters | Integration | Real DB/services |
| API | E2E | Full application |

## References

- [Hexagonal Architecture by Alistair Cockburn](https://alistair.cockburn.us/hexagonal-architecture/)
- [Ports and Adapters Pattern](https://herbertograca.com/2017/09/14/ports-adapters-architecture/)
- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
