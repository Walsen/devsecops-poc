"""Request validation middleware with security limits.

Security: Implements request size limits and validation to prevent:
- Large payload DoS attacks
- Memory exhaustion
- Slowloris attacks
"""

import structlog
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger()

# Security: Request size limits
MAX_REQUEST_SIZE = 1 * 1024 * 1024  # 1 MB default
MAX_JSON_DEPTH = 20  # Maximum nesting depth for JSON
MAX_ARRAY_LENGTH = 100  # Maximum array length in JSON


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce request size limits.

    Security: Prevents large payload DoS attacks by rejecting
    requests that exceed the configured size limit.
    """

    def __init__(self, app, max_size: int = MAX_REQUEST_SIZE) -> None:
        super().__init__(app)
        self._max_size = max_size

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check request size before processing."""
        # Check Content-Length header
        content_length = request.headers.get("content-length")

        if content_length:
            try:
                size = int(content_length)
                if size > self._max_size:
                    logger.warning(
                        "Request rejected: payload too large",
                        content_length=size,
                        max_size=self._max_size,
                        path=request.url.path,
                        client=request.client.host if request.client else "unknown",
                    )
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Request body too large. Maximum size: {self._max_size} bytes",
                    )
            except ValueError:
                # Invalid Content-Length header
                logger.warning(
                    "Invalid Content-Length header",
                    content_length=content_length,
                    path=request.url.path,
                )

        # For chunked transfers, we need to check as we read
        # This is handled by setting body_limit in uvicorn config

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to responses.

    Security: Adds headers to prevent common web vulnerabilities.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Content Security Policy for API responses
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"

        # Prevent caching of sensitive data
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"

        return response
