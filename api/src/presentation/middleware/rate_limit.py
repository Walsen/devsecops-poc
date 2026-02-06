"""Per-user rate limiting middleware.

Security: Implements rate limiting per authenticated user to prevent:
- API abuse by individual users
- Resource exhaustion attacks
- Brute force attempts
"""

import time
from collections import defaultdict
from dataclasses import dataclass

import structlog
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = structlog.get_logger()


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10  # Max requests in 1 second


@dataclass
class UserRateState:
    """Rate limit state for a user."""

    minute_count: int = 0
    minute_reset: float = 0
    hour_count: int = 0
    hour_reset: float = 0
    last_request: float = 0
    burst_count: int = 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Per-user rate limiting middleware.

    Security: Limits requests per user (from JWT sub claim) rather than
    just per IP, preventing abuse from authenticated users.

    Rate limits:
    - 60 requests per minute (default)
    - 1000 requests per hour (default)
    - 10 requests per second burst limit
    """

    def __init__(
        self,
        app,
        config: RateLimitConfig | None = None,
        exclude_paths: list[str] | None = None,
    ) -> None:
        super().__init__(app)
        self._config = config or RateLimitConfig()
        self._exclude_paths = exclude_paths or ["/health", "/", "/docs", "/openapi.json"]
        self._user_states: dict[str, UserRateState] = defaultdict(UserRateState)
        self._ip_states: dict[str, UserRateState] = defaultdict(UserRateState)

    async def dispatch(self, request: Request, call_next) -> Response:
        """Check rate limits before processing request."""
        # Skip rate limiting for excluded paths
        if request.url.path in self._exclude_paths:
            return await call_next(request)

        # Get user identifier (prefer user_id from auth, fallback to IP)
        user_id = self._get_user_id(request)
        client_ip = request.client.host if request.client else "unknown"

        # Use user_id if authenticated, otherwise use IP
        identifier = user_id or client_ip
        is_authenticated = user_id is not None

        # Check rate limits
        state = self._user_states[identifier] if is_authenticated else self._ip_states[identifier]
        now = time.time()

        # Reset counters if windows have passed
        if now > state.minute_reset:
            state.minute_count = 0
            state.minute_reset = now + 60

        if now > state.hour_reset:
            state.hour_count = 0
            state.hour_reset = now + 3600

        # Check burst limit (requests in last second)
        if now - state.last_request < 1:
            state.burst_count += 1
            if state.burst_count > self._config.burst_limit:
                logger.warning(
                    "Rate limit exceeded (burst)",
                    identifier=identifier[:20] if len(identifier) > 20 else identifier,
                    burst_count=state.burst_count,
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please slow down.",
                    headers={"Retry-After": "1"},
                )
        else:
            state.burst_count = 1

        state.last_request = now

        # Check minute limit
        state.minute_count += 1
        if state.minute_count > self._config.requests_per_minute:
            retry_after = int(state.minute_reset - now)
            logger.warning(
                "Rate limit exceeded (minute)",
                identifier=identifier[:20] if len(identifier) > 20 else identifier,
                minute_count=state.minute_count,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

        # Check hour limit
        state.hour_count += 1
        if state.hour_count > self._config.requests_per_hour:
            retry_after = int(state.hour_reset - now)
            logger.warning(
                "Rate limit exceeded (hour)",
                identifier=identifier[:20] if len(identifier) > 20 else identifier,
                hour_count=state.hour_count,
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Hourly rate limit exceeded. Try again in {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self._config.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, self._config.requests_per_minute - state.minute_count)
        )
        response.headers["X-RateLimit-Reset"] = str(int(state.minute_reset))

        return response

    def _get_user_id(self, request: Request) -> str | None:
        """
        Extract user ID from request state (set by auth middleware).

        Returns None if user is not authenticated.
        """
        # Check if auth middleware has set the user
        if hasattr(request.state, "user") and request.state.user:
            return request.state.user.user_id

        # Fallback: try to extract from Authorization header
        # This is a simplified check - full validation happens in auth middleware
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            # Return a hash of the token as identifier (not the actual token)
            import hashlib

            token = auth_header[7:]
            return hashlib.sha256(token.encode()).hexdigest()[:32]

        return None
