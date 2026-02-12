from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from .config import settings
from .infrastructure.logging import configure_logging
from .presentation.api.dependencies import get_database
from .presentation.api.v1 import auth, certifications, health, messages
from .presentation.middleware import (
    CorrelationIdMiddleware,
    CSRFMiddleware,
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)

# Configure enterprise logging
configure_logging(settings.service_name)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting application", service=settings.service_name)

    # Initialize database and create tables
    db = get_database()
    try:
        logger.info(
            "Creating database tables",
            db_host=settings.db_host,
            db_name=settings.db_name,
        )
        await db.create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(
            "Failed to create database tables",
            error=str(e),
            error_type=type(e).__name__,
            db_host=settings.db_host,
            db_name=settings.db_name,
            exc_info=True,
        )
        raise

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

# Security: Add middleware (order matters - first added = last executed)
# CSRF protection for state-changing requests
if settings.csrf_enabled:
    app.add_middleware(
        CSRFMiddleware,
        secret_key=settings.secret_key,
        secure_cookies=not settings.debug,  # Secure cookies in production
    )
app.add_middleware(RateLimitMiddleware)  # Per-user rate limiting
app.add_middleware(RequestSizeLimitMiddleware, max_size=1 * 1024 * 1024)  # 1 MB limit
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CorrelationIdMiddleware)  # Request tracing (runs first)

# Include routers
app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(messages.router, prefix="/api/v1")
app.include_router(certifications.router, prefix="/api/v1")


@app.get("/")
def root() -> dict:
    return {
        "service": settings.service_name,
        "version": "0.1.0",
        "docs": "/docs",
    }
