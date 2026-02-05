from typing import AsyncGenerator

from fastapi import Depends

from ...application.commands import ScheduleMessageCommand
from ...application.queries import GetMessageQuery
from ...config import settings
from ...infrastructure.messaging.kinesis_publisher import KinesisEventPublisher
from ...infrastructure.persistence.database import Database
from ...infrastructure.persistence.message_repository import PostgresMessageRepository
from ...infrastructure.persistence.unit_of_work import SqlAlchemyUnitOfWork

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
    )


async def get_schedule_command(
    session=Depends(get_session),
    publisher: KinesisEventPublisher = Depends(get_event_publisher),
) -> ScheduleMessageCommand:
    repository = PostgresMessageRepository(session)
    unit_of_work = SqlAlchemyUnitOfWork(session)
    return ScheduleMessageCommand(repository, publisher, unit_of_work)


async def get_message_query(session=Depends(get_session)) -> GetMessageQuery:
    repository = PostgresMessageRepository(session)
    return GetMessageQuery(repository)
