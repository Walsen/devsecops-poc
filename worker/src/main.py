import asyncio
import signal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .consumer import KinesisConsumer
from .infrastructure.adapters import (
    AgentPublisher,
    DirectPublisher,
    SqlAlchemyMessageRepository,
)
from .infrastructure.idempotency import get_idempotency_service
from .infrastructure.logging import configure_logging
from .processor import MessageProcessor

# Configure enterprise logging
configure_logging(settings.service_name)

logger = structlog.get_logger()


def create_publisher():
    """Create the appropriate publisher based on configuration."""
    if settings.use_ai_agent:
        logger.info("Using AI Agent publisher for intelligent content adaptation")
        return AgentPublisher()
    else:
        logger.info("Using Direct publisher for simple delivery")
        return DirectPublisher()


async def main() -> None:
    """Main entry point for the worker."""
    logger.info("Starting worker", service=settings.service_name)

    # Initialize database
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    async with session_factory() as session:
        # Wire up dependencies (Composition Root)
        message_repository = SqlAlchemyMessageRepository(session)
        publisher = create_publisher()
        idempotency = get_idempotency_service()

        processor = MessageProcessor(
            message_repository=message_repository,
            publisher=publisher,
        )
        consumer = KinesisConsumer(
            processor=processor,
            idempotency=idempotency,
        )

        # Handle shutdown signals
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(consumer.stop()))

        try:
            await consumer.start()
        except asyncio.CancelledError:
            logger.info("Worker cancelled")
        finally:
            await engine.dispose()
            logger.info("Worker shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
