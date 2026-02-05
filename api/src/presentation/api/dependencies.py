from collections.abc import AsyncGenerator

from fastapi import Depends

from ...application.ports.inbound import (
    GetCertificationUseCase,
    GetMessageUseCase,
    ListCertificationTypesUseCase,
    ScheduleMessageUseCase,
    SubmitCertificationUseCase,
)
from ...application.services import (
    GetCertificationService,
    GetMessageService,
    ListCertificationTypesService,
    ScheduleMessageService,
    SubmitCertificationService,
)
from ...config import settings
from ...infrastructure.adapters import (
    KinesisEventPublisher,
    PostgresCertificationRepository,
    PostgresMessageRepository,
    SqlAlchemyUnitOfWork,
)
from ...infrastructure.persistence.database import Database

# Singleton database instance
_database: Database | None = None


def get_database() -> Database:
    global _database
    if _database is None:
        _database = Database(settings.database_url)
    return _database


async def get_session() -> AsyncGenerator:
    db = get_database()
    session = db.session()
    try:
        yield session
    finally:
        await session.close()


def get_event_publisher() -> KinesisEventPublisher:
    return KinesisEventPublisher(
        stream_name=settings.kinesis_stream_name,
        region=settings.aws_region,
        endpoint_url=settings.aws_endpoint_url,
    )


async def get_schedule_message_use_case(
    session=Depends(get_session),
    publisher: KinesisEventPublisher = Depends(get_event_publisher),
) -> ScheduleMessageUseCase:
    """Dependency injection for ScheduleMessageUseCase."""
    repository = PostgresMessageRepository(session)
    unit_of_work = SqlAlchemyUnitOfWork(session)
    return ScheduleMessageService(repository, publisher, unit_of_work)


async def get_message_use_case(session=Depends(get_session)) -> GetMessageUseCase:
    """Dependency injection for GetMessageUseCase."""
    repository = PostgresMessageRepository(session)
    return GetMessageService(repository)


async def get_certification_service(
    session=Depends(get_session),
    publisher: KinesisEventPublisher = Depends(get_event_publisher),
) -> SubmitCertificationUseCase:
    """Dependency injection for SubmitCertificationUseCase."""
    repository = PostgresCertificationRepository(session)
    unit_of_work = SqlAlchemyUnitOfWork(session)
    return SubmitCertificationService(repository, publisher, unit_of_work)


async def get_certification_use_case(
    session=Depends(get_session),
) -> GetCertificationUseCase:
    """Dependency injection for GetCertificationUseCase."""
    repository = PostgresCertificationRepository(session)
    return GetCertificationService(repository)


def get_list_certification_types_use_case() -> ListCertificationTypesUseCase:
    """Dependency injection for ListCertificationTypesUseCase."""
    return ListCertificationTypesService()
