import asyncio
import signal

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .consumer import KinesisConsumer
from .processor import MessageProcessor

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)

logger = structlog.get_logger()


async def main() -> None:
    """Main entry point for the worker."""
    logger.info("Starting worker", service=settings.service_name)

    # Initialize database
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    async with session_factory() as session:
        processor = MessageProcessor(session)
        consumer = KinesisConsumer(processor)

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
