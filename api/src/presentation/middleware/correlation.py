"""
Correlation ID middleware for request tracing.

Adds a unique correlation ID to each request for distributed tracing.
The ID is:
- Extracted from X-Request-ID header if present
- Generated if not present
- Added to all logs via structlog contextvars
- Returned in response headers
"""

from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ...infrastructure.logging import set_correlation_id

logger = structlog.get_logger()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle correlation IDs for request tracing.

    Extracts or generates a correlation ID and:
    1. Sets it in the context variable for logging
    2. Binds it to structlog context
    3. Returns it in response headers
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Get or generate correlation ID
        correlation_id = request.headers.get(
            "X-Request-ID",
            request.headers.get("X-Correlation-ID", str(uuid4())),
        )

        # Set in context variable
        set_correlation_id(correlation_id)

        # Bind to structlog context for all logs in this request
        with structlog.contextvars.bound_contextvars(
            correlation_id=correlation_id,
            method=request.method,
            path=request.url.path,
        ):
            logger.info(
                "Request started",
                client_ip=request.client.host if request.client else None,
            )

            response = await call_next(request)

            logger.info(
                "Request completed",
                status_code=response.status_code,
            )

        # Add correlation ID to response headers
        response.headers["X-Request-ID"] = correlation_id
        response.headers["X-Correlation-ID"] = correlation_id

        return response
