from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from .config import settings
from .presentation.api.dependencies import get_database
from .presentation.api.v1 import certifications, health, messages

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting application", service=settings.service_name)

    # Initialize database
    db = get_database()
    if settings.debug:
        await db.create_tables()

    yield

    # Cleanup
    await db.close()
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Omnichannel Publisher API",
    description="Schedule and deliver messages across multiple channels",
    version="0.1.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(health.router)
app.include_router(messages.router, prefix="/api/v1")
app.include_router(certifications.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "service": settings.service_name,
        "version": "0.1.0",
        "docs": "/docs",
    }
