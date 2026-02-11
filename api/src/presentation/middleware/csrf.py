"""CSRF protection middleware.

Security: Implements CSRF (Cross-Site Request Forgery) protection using
the Double Submit Cookie pattern with signed tokens.

How it works:
1. Server generates a signed CSRF token and sets it in a cookie
2. Client must include the same token in the X-CSRF-Token header
3. Server validates that cookie token matches header token
4. Tokens are signed with HMAC to prevent tampering

Protected methods: POST, PUT, PATCH, DELETE
Safe methods: GET, HEAD, OPTIONS (no state changes)
"""

import hashlib
import hmac
import secrets
import time
from typing import Any

import structlog
from fastapi import Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger()

# CSRF configuration
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_LENGTH = 32
CSRF_TOKEN_TTL = 3600  # 1 hour


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection using Double Submit Cookie pattern.

    Security features:
    - Signed tokens prevent tampering
    - Time-limited tokens prevent replay attacks
    - SameSite=Strict cookie prevents cross-origin requests
    - Secure flag ensures HTTPS-only in production
    """

    # Methods that require CSRF protection (state-changing)
    PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    # Paths exempt from CSRF (e.g., login endpoints that use other auth)
    EXEMPT_PATHS: set[str] = {
        "/health",
        "/ready",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    def __init__(
        self,
        app: Any,
        secret_key: str,
        secure_cookies: bool = True,
        exempt_paths: set[str] | None = None,
    ) -> None:
        """
        Initialize CSRF middleware.

        Args:
            app: ASGI application
            secret_key: Secret key for signing tokens (use settings.secret_key)
            secure_cookies: Set Secure flag on cookies (True for production)
            exempt_paths: Additional paths to exempt from CSRF protection
        """
        super().__init__(app)
        self._secret_key = secret_key.encode()
        self._secure_cookies = secure_cookies
        self._exempt_paths = self.EXEMPT_PATHS.copy()
        if exempt_paths:
            self._exempt_paths.update(exempt_paths)

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        """Process request with CSRF validation."""
        # Skip CSRF for safe methods
        if request.method not in self.PROTECTED_METHODS:
            response = await call_next(request)
            # Set CSRF cookie on GET requests for subsequent POST/PUT/etc
            if request.method == "GET" and not self._is_exempt(request.url.path):
                self._set_csrf_cookie(response)
            return response

        # Skip CSRF for exempt paths
        if self._is_exempt(request.url.path):
            return await call_next(request)

        # Validate CSRF token
        if not self._validate_csrf(request):
            logger.warning(
                "CSRF validation failed",
                path=request.url.path,
                method=request.method,
                client=request.client.host if request.client else "unknown",
            )
            # Return JSONResponse directly instead of raising HTTPException
            # This is required because BaseHTTPMiddleware doesn't properly
            # handle exceptions - they propagate before exception handlers
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "CSRF token missing or invalid"},
            )

        response = await call_next(request)

        # Rotate token after successful state-changing request
        self._set_csrf_cookie(response)

        return response

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from CSRF protection."""
        # Exact match
        if path in self._exempt_paths:
            return True
        # Prefix match for API docs
        if path.startswith("/docs") or path.startswith("/redoc"):
            return True
        return False

    def _generate_token(self) -> str:
        """Generate a signed CSRF token with timestamp."""
        # Random token
        random_bytes = secrets.token_bytes(CSRF_TOKEN_LENGTH)
        random_hex = random_bytes.hex()

        # Timestamp for expiration
        timestamp = str(int(time.time()))

        # Create signature
        message = f"{random_hex}.{timestamp}"
        signature = self._sign(message)

        return f"{random_hex}.{timestamp}.{signature}"

    def _sign(self, message: str) -> str:
        """Create HMAC signature for message."""
        return hmac.new(
            self._secret_key,
            message.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]  # Truncate for shorter tokens

    def _validate_token(self, token: str) -> bool:
        """Validate CSRF token signature and expiration."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return False

            random_hex, timestamp, signature = parts

            # Verify signature
            message = f"{random_hex}.{timestamp}"
            expected_signature = self._sign(message)

            if not hmac.compare_digest(signature, expected_signature):
                logger.debug("CSRF signature mismatch")
                return False

            # Check expiration
            token_time = int(timestamp)
            if time.time() - token_time > CSRF_TOKEN_TTL:
                logger.debug("CSRF token expired")
                return False

            return True

        except (ValueError, AttributeError):
            return False

    def _validate_csrf(self, request: Request) -> bool:
        """Validate CSRF token from cookie matches header."""
        # Get token from cookie
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        if not cookie_token:
            logger.debug("CSRF cookie missing")
            return False

        # Get token from header
        header_token = request.headers.get(CSRF_HEADER_NAME)
        if not header_token:
            logger.debug("CSRF header missing")
            return False

        # Tokens must match exactly
        if not hmac.compare_digest(cookie_token, header_token):
            logger.debug("CSRF cookie/header mismatch")
            return False

        # Validate token signature and expiration
        return self._validate_token(cookie_token)

    def _set_csrf_cookie(self, response: Response) -> None:
        """Set CSRF token cookie on response."""
        token = self._generate_token()

        response.set_cookie(
            key=CSRF_COOKIE_NAME,
            value=token,
            max_age=CSRF_TOKEN_TTL,
            httponly=False,  # Must be readable by JavaScript
            secure=self._secure_cookies,
            samesite="strict",  # Prevent cross-origin requests
            path="/",
        )
