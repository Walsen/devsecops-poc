# Architecture Principles

## Hexagonal Architecture (Ports & Adapters)

All services MUST follow hexagonal architecture:

### Layer Structure
```
src/
├── domain/           # Core business logic (NO external dependencies)
│   ├── entities/     # Aggregate roots and entities
│   ├── value_objects/# Immutable value objects
│   └── ports/        # Abstract interfaces (outbound)
├── application/      # Use cases and orchestration
│   ├── ports/
│   │   ├── inbound/  # Use case interfaces
│   │   └── outbound/ # Repository/service interfaces
│   ├── services/     # Use case implementations
│   └── dtos/         # Data transfer objects
├── infrastructure/   # External concerns
│   └── adapters/     # Concrete implementations of ports
└── presentation/     # API controllers, CLI, etc.
```

### Rules
1. **Domain layer** has ZERO external dependencies (no SQLAlchemy, no boto3, no HTTP clients)
2. **Application layer** depends only on domain and ports (interfaces)
3. **Infrastructure layer** implements ports - this is where SQL, API calls, etc. live
4. **Dependencies flow inward** - outer layers depend on inner layers, never the reverse
5. **Use constructor injection** for all dependencies
6. **Composition root** (main.py) wires all dependencies

### Anti-Patterns to Avoid
- ❌ Raw SQL in application or domain layers
- ❌ Direct imports from infrastructure in application layer
- ❌ Global singletons for services (use dependency injection)
- ❌ Domain entities with database annotations
- ❌ Use cases that directly instantiate infrastructure

### Correct Patterns
- ✅ Define ports (interfaces) in domain/application layer
- ✅ Implement adapters in infrastructure layer
- ✅ Inject dependencies via constructor
- ✅ Wire dependencies in composition root (main.py)
- ✅ Domain entities are pure Python dataclasses

## Clean Code Principles

### Naming
- Use descriptive, intention-revealing names
- Classes: `PascalCase` (nouns) - `MessageRepository`, `UserService`
- Functions: `snake_case` (verbs) - `get_by_id`, `schedule_message`
- Constants: `UPPER_SNAKE_CASE` - `MAX_RETRY_COUNT`
- Private members: prefix with `_` - `_session`, `_cache`

### Functions
- Single responsibility - do one thing well
- Keep functions small (< 20 lines preferred)
- Maximum 3-4 parameters (use dataclasses/DTOs for more)
- No side effects in query methods
- Command-query separation (CQS)

### Classes
- Single Responsibility Principle (SRP)
- Open/Closed Principle - open for extension, closed for modification
- Liskov Substitution - subtypes must be substitutable
- Interface Segregation - many specific interfaces over one general
- Dependency Inversion - depend on abstractions, not concretions

### Code Organization
- One class per file (with exceptions for small related classes)
- Group imports: stdlib, third-party, local
- Keep files under 300 lines
- Extract complex logic into well-named helper methods

## Enterprise Patterns

### Repository Pattern
```python
# Port (interface)
class MessageRepository(ABC):
    @abstractmethod
    async def get_by_id(self, id: UUID) -> Message | None: ...
    
    @abstractmethod
    async def save(self, message: Message) -> None: ...

# Adapter (implementation)
class PostgresMessageRepository(MessageRepository):
    def __init__(self, session: AsyncSession):
        self._session = session
```

### Unit of Work Pattern
```python
class UnitOfWork(ABC):
    @abstractmethod
    async def commit(self) -> None: ...
    
    @abstractmethod
    async def rollback(self) -> None: ...
```

### Service Layer Pattern
```python
class ScheduleMessageService:
    def __init__(
        self,
        repository: MessageRepository,
        publisher: EventPublisher,
        uow: UnitOfWork,
    ):
        self._repository = repository
        self._publisher = publisher
        self._uow = uow
```

### Factory Pattern
Use factories for complex object creation:
```python
class ChannelGatewayFactory:
    @staticmethod
    def create(channel_type: ChannelType) -> ChannelGateway:
        match channel_type:
            case ChannelType.FACEBOOK:
                return FacebookGateway()
            # ...
```

### Strategy Pattern
Use for interchangeable algorithms (e.g., DirectPublisher vs AgentPublisher)

## References
- Architecture details: #[[file:docs/architecture.md]]
