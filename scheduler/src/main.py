import asyncio
import signal

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .config import settings
from .publisher import EventPublisher
from .scheduler import MessageScheduler

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

# Global state
_running = True
_engine = None
_session_factory = None


async def poll_job() -> None:
    """Job that runs on schedule to check for due messages."""
    global _session_factory

    if _session_factory is None:
        return

    async with _session_factory() as session:
        publisher = EventPublisher()
        scheduler = MessageScheduler(session, publisher)
        await scheduler.process_due_messages()


async def main() -> None:
    """Main entry point for the scheduler service."""
    global _running, _engine, _session_factory

    logger.info("Starting scheduler", service=settings.service_name)

    # Initialize database
    _engine = create_async_engine(settings.database_url, echo=False)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession)

    # Set up APScheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        poll_job,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="poll_due_messages",
        max_instances=1,  # Prevent overlapping runs
    )

    # Handle shutdown signals
    loop = asyncio.get_event_loop()

    def shutdown():
        global _running
        _running = False
        scheduler.shutdown(wait=False)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown)

    # Start scheduler
    scheduler.start()
    logger.info(
        "Scheduler started",
        poll_interval=settings.poll_interval_seconds,
    )

    # Run initial poll immediately
    await poll_job()

    # Keep running until shutdown
    try:
        while _running:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    finally:
        if _engine:
            await _engine.dispose()
        logger.info("Scheduler shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
