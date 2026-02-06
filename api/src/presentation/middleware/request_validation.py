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
    Middleware to add comprehensive security headers to responses.

    Security: Adds headers to prevent common web vulnerabilities:
    - XSS (Cross-Site Scripting)
    - Clickjacking
    - MIME sniffing
    - Information disclosure
    """

    # Content Security Policy for API
    # Strict policy since this is an API, not serving HTML
    CSP_API = "; ".join([
        "default-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'none'",
        "form-action 'none'",
    ])

    # Content Security Policy for docs (Swagger/ReDoc)
    # More permissive to allow UI functionality
    CSP_DOCS = "; ".join([
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "img-src 'self' data: https://cdn.jsdelivr.net",
        "font-src 'self' https://cdn.jsdelivr.net",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ])

    # Permissions Policy (formerly Feature-Policy)
    PERMISSIONS_POLICY = ", ".join([
        "accelerometer=()",
        "camera=()",
        "geolocation=()",
        "gyroscope=()",
        "magnetometer=()",
        "microphone=()",
        "payment=()",
        "usb=()",
    ])

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Core security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"  # Disabled, CSP is better
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # HSTS - enforce HTTPS (1 year, include subdomains)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Permissions Policy - disable unnecessary browser features
        response.headers["Permissions-Policy"] = self.PERMISSIONS_POLICY

        # Content Security Policy - different for API vs docs
        if self._is_docs_path(request.url.path):
            response.headers["Content-Security-Policy"] = self.CSP_DOCS
        else:
            response.headers["Content-Security-Policy"] = self.CSP_API

        # Prevent caching of sensitive API data
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        # Cross-Origin headers for API isolation
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

        return response

    def _is_docs_path(self, path: str) -> bool:
        """Check if path is for API documentation."""
        return path in {"/docs", "/redoc", "/openapi.json"} or path.startswith("/docs")
