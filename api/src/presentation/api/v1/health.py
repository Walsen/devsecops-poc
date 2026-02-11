import structlog
from fastapi import APIRouter

from ....infrastructure.logging import Timer
from ...api.dependencies import get_database

router = APIRouter(tags=["health"])
logger = structlog.get_logger()


@router.get("/health", summary="Health check")
async def health() -> dict:
    """Basic health check for load balancer."""
    return {"status": "healthy"}


@router.get("/health/ready", summary="Readiness check")
async def readiness() -> dict:
    """Readiness check - verifies dependencies are available."""
    checks = {}

    # Check database connectivity
    try:
        with Timer() as t:
            db = get_database()
            async with db.session() as session:
                await session.execute("SELECT 1")
        checks["database"] = {"status": "healthy", "latency_ms": t.duration_ms}
    except Exception as e:
        logger.error("Database health check failed", error=str(e))
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    # Determine overall status
    all_healthy = all(c.get("status") == "healthy" for c in checks.values())

    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
    }
