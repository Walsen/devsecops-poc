from typing import AsyncGenerator

from fastapi import Depends

from ...application.ports.inbound import GetMessageUseCase, ScheduleMessageUseCase
from ...application.services import GetMessageService, ScheduleMessageService
from ...config import settings
from ...infrastructure.adapters import (
    KinesisEventPublisher,
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
