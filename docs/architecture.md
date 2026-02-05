# Architecture & Enterprise Patterns

## Overview

This document describes the architectural patterns and clean code principles used in the Omnichannel Publisher platform.

## Architecture Pattern: Clean Architecture + CQRS-lite

```
┌─────────────────────────────────────────────────────────┐
│                    Presentation Layer                    │
│              (FastAPI routes, DTOs, OpenAPI)            │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                   Application Layer                      │
│         (Use Cases, Commands, Queries, DTOs)            │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                     Domain Layer                         │
│      (Entities, Value Objects, Domain Services)         │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────┐
│                 Infrastructure Layer                     │
│    (Repositories, External APIs, DB, Message Queue)     │
└─────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

#### Presentation Layer
- HTTP request/response handling
- Input validation and serialization
- OpenAPI documentation
- Authentication/authorization middleware
- No business logic

#### Application Layer
- Use case orchestration
- Transaction boundaries
- DTO transformations
- Coordinates domain objects and infrastructure

#### Domain Layer
- Core business logic
- Entities and aggregates
- Value objects with validation
- Domain events
- Repository interfaces (ports)
- Zero external dependencies

#### Infrastructure Layer
- Database implementations
- External API clients (Meta, AWS services)
- Message queue producers/consumers
- Caching implementations

## Key Patterns

| Pattern | Purpose | Example |
|---------|---------|---------|
| Repository | Abstract data access | `MessageRepository` interface, `PostgresMessageRepository` impl |
| Unit of Work | Transaction management | Wrap multiple repo operations in single transaction |
| Use Cases | Single responsibility business logic | `ScheduleMessageUseCase`, `PublishToChannelUseCase` |
| Domain Events | Decouple side effects | `MessageScheduled` → triggers Kinesis publish |
| Value Objects | Immutable, validated types | `ChannelType`, `MessageContent`, `RecipientId` |
| DTOs | Layer boundary contracts | `CreateMessageRequest`, `MessageResponse` |
| Dependency Injection | Testability, loose coupling | Inject repos/services into use cases |

## Folder Structure

```
api/
├── src/
│   ├── domain/                 # Pure business logic, no dependencies
│   │   ├── entities/
│   │   │   ├── message.py      # Message aggregate root
│   │   │   └── channel.py
│   │   ├── value_objects/
│   │   │   ├── channel_type.py # Enum + validation
│   │   │   └── content.py
│   │   ├── events/
│   │   │   └── message_events.py
│   │   ├── repositories/       # Abstract interfaces only
│   │   │   └── message_repository.py
│   │   └── services/           # Domain services
│   │       └── scheduling_service.py
│   │
│   ├── application/            # Orchestration, use cases
│   │   ├── commands/
│   │   │   └── schedule_message.py
│   │   ├── queries/
│   │   │   └── get_message_status.py
│   │   ├── dtos/
│   │   │   └── message_dto.py
│   │   └── interfaces/         # Port interfaces
│   │       └── channel_gateway.py
│   │
│   ├── infrastructure/         # Concrete implementations
│   │   ├── persistence/
│   │   │   ├── postgres/
│   │   │   │   ├── models.py   # SQLAlchemy models
│   │   │   │   └── message_repository.py
│   │   │   └── unit_of_work.py
│   │   ├── messaging/
│   │   │   └── kinesis_publisher.py
│   │   └── external/
│   │       ├── meta_gateway.py # Facebook/Instagram/WhatsApp
│   │       └── ses_gateway.py
│   │
│   └── presentation/           # FastAPI layer
│       ├── api/
│       │   ├── v1/
│       │   │   ├── messages.py
│       │   │   └── channels.py
│       │   └── dependencies.py # DI container
│       └── middleware/
│           └── error_handler.py
│
├── tests/
│   ├── unit/                   # Domain + application tests
│   ├── integration/            # Repository + external API tests
│   └── e2e/                    # Full API tests
│
└── pyproject.toml
```

## Code Examples

### Domain Entity

```python
# domain/entities/message.py
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Message:
    id: MessageId
    content: MessageContent
    channels: list[ChannelType]
    scheduled_at: datetime
    status: MessageStatus
    
    def schedule(self) -> list[DomainEvent]:
        """Schedule the message for delivery."""
        self.status = MessageStatus.SCHEDULED
        return [MessageScheduled(self.id, self.scheduled_at)]
    
    def mark_delivered(self, channel: ChannelType) -> list[DomainEvent]:
        """Mark delivery complete for a channel."""
        # Domain logic here
        return [MessageDelivered(self.id, channel)]
```

### Repository Interface (Port)

```python
# domain/repositories/message_repository.py
from typing import Protocol

class MessageRepository(Protocol):
    """Abstract interface for message persistence."""
    
    async def save(self, message: Message) -> None: ...
    async def get_by_id(self, id: MessageId) -> Message | None: ...
    async def get_pending(self, before: datetime) -> list[Message]: ...
```

### Use Case (Command)

```python
# application/commands/schedule_message.py
from dataclasses import dataclass

@dataclass
class ScheduleMessageDTO:
    content: str
    channels: list[str]
    scheduled_at: datetime
    recipient_id: str

class ScheduleMessageCommand:
    """Use case for scheduling a message."""
    
    def __init__(
        self,
        repo: MessageRepository,
        event_bus: EventBus,
        unit_of_work: UnitOfWork,
    ):
        self._repo = repo
        self._event_bus = event_bus
        self._uow = unit_of_work
    
    async def execute(self, dto: ScheduleMessageDTO) -> MessageId:
        # Create domain entity
        message = Message.create(
            content=MessageContent(dto.content),
            channels=[ChannelType(c) for c in dto.channels],
            scheduled_at=dto.scheduled_at,
        )
        
        # Execute domain logic
        events = message.schedule()
        
        # Persist within transaction
        async with self._uow:
            await self._repo.save(message)
            await self._uow.commit()
        
        # Publish domain events (outside transaction)
        await self._event_bus.publish(events)
        
        return message.id
```

### Infrastructure Implementation

```python
# infrastructure/persistence/postgres/message_repository.py
from sqlalchemy.ext.asyncio import AsyncSession

class PostgresMessageRepository:
    """Concrete implementation of MessageRepository for PostgreSQL."""
    
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def save(self, message: Message) -> None:
        model = MessageModel.from_entity(message)
        self._session.add(model)
        await self._session.flush()
    
    async def get_by_id(self, id: MessageId) -> Message | None:
        result = await self._session.get(MessageModel, str(id))
        return result.to_entity() if result else None
```

### Presentation Layer

```python
# presentation/api/v1/messages.py
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("/", response_model=MessageResponse, status_code=201)
async def schedule_message(
    request: CreateMessageRequest,
    command: ScheduleMessageCommand = Depends(get_schedule_command),
) -> MessageResponse:
    """Schedule a message for delivery."""
    message_id = await command.execute(
        ScheduleMessageDTO(
            content=request.content,
            channels=request.channels,
            scheduled_at=request.scheduled_at,
            recipient_id=request.recipient_id,
        )
    )
    return MessageResponse(id=str(message_id), status="scheduled")
```

## Benefits

- **Testability**: Domain logic is testable without DB/HTTP dependencies
- **Flexibility**: Easy to swap implementations (Postgres → DynamoDB, Kinesis → SQS)
- **Maintainability**: Clear boundaries make onboarding easier
- **Explicit Use Cases**: Business operations are documented in code
- **Separation of Concerns**: Each layer has a single responsibility

## Testing Strategy

| Layer | Test Type | Dependencies |
|-------|-----------|--------------|
| Domain | Unit tests | None (pure Python) |
| Application | Unit tests | Mocked repositories |
| Infrastructure | Integration tests | Real DB/services |
| Presentation | E2E tests | Full application |

## References

- [Clean Architecture by Robert C. Martin](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Domain-Driven Design by Eric Evans](https://www.domainlanguage.com/ddd/)
- [CQRS Pattern](https://martinfowler.com/bliki/CQRS.html)
