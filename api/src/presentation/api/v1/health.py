from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Health check")
async def health() -> dict:
    """Basic health check for load balancer."""
    return {"status": "healthy"}


@router.get("/health/ready", summary="Readiness check")
async def readiness() -> dict:
    """Readiness check - verifies dependencies are available."""
    # TODO: Add actual dependency checks (DB, Kinesis)
    return {"status": "ready"}
