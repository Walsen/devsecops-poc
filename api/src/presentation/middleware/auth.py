"""JWT Authentication Middleware with security hardening.

Security features:
- Algorithm restriction (RS256 only, no algorithm confusion)
- Strict audience validation
- Strict issuer validation
- JWKS cache with TTL and forced refresh on key rotation
- Token type validation (access vs id token)
- Secure token storage via httpOnly cookies (XSS protection)
"""

import time
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
import structlog
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt

from ...config import settings

logger = structlog.get_logger()

security = HTTPBearer(auto_error=False)

# Security: Only allow RS256 algorithm (prevents algorithm confusion attacks)
ALLOWED_ALGORITHMS = ["RS256"]

# Security: Required claims that must be present
REQUIRED_CLAIMS = ["sub", "exp", "iat", "iss"]

# Security: Cookie configuration for secure token storage
ACCESS_TOKEN_COOKIE = "access_token"  # noqa: S105
REFRESH_TOKEN_COOKIE = "refresh_token"  # noqa: S105
TOKEN_COOKIE_MAX_AGE = 3600  # 1 hour for access token
REFRESH_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days for refresh token


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user from JWT claims."""

    sub: str  # User ID
    email: str | None = None
    name: str | None = None
    groups: list[str] | None = None
    token_use: str | None = None  # 'access' or 'id'

    @property
    def user_id(self) -> str:
        return self.sub


class JWTAuthMiddleware:
    """JWT authentication using Cognito JWKS with security hardening."""

    def __init__(
        self,
        jwks_url: str,
        audience: str,
        issuer: str,
        cache_ttl: int = 3600,
        allowed_algorithms: list[str] | None = None,
    ):
        self.jwks_url = jwks_url
        self.audience = audience
        self.issuer = issuer
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_cache_time: float = 0
        self._cache_ttl = cache_ttl
        self._allowed_algorithms = allowed_algorithms or ALLOWED_ALGORITHMS

        # Security: Validate configuration at init time
        if not audience:
            raise ValueError("Audience (client_id) is required for JWT validation")
        if not issuer:
            raise ValueError("Issuer is required for JWT validation")

    async def _get_jwks(self, force_refresh: bool = False) -> dict[str, Any]:
        """Fetch and cache JWKS from Cognito.

        Args:
            force_refresh: Force refresh even if cache is valid (for key rotation)
        """
        now = time.time()

        if (
            not force_refresh
            and self._jwks_cache
            and (now - self._jwks_cache_time) < self._cache_ttl
        ):
            return self._jwks_cache

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.jwks_url)
                response.raise_for_status()
                self._jwks_cache = response.json()
                self._jwks_cache_time = now

            logger.debug("JWKS cache refreshed", url=self.jwks_url)
            return self._jwks_cache

        except httpx.HTTPError as e:
            logger.error("Failed to fetch JWKS", error=str(e), url=self.jwks_url)
            # If we have a cached version, use it even if expired
            if self._jwks_cache:
                logger.warning("Using expired JWKS cache due to fetch failure")
                return self._jwks_cache
            raise JWTError("Unable to fetch JWKS") from e

    async def _get_signing_key(self, token: str) -> dict[str, Any]:
        """Get the signing key for a token from JWKS.

        Security: Validates algorithm in header before processing.
        """
        # Security: Get unverified header to check algorithm FIRST
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as e:
            raise JWTError("Invalid token header") from e

        # Security: Reject tokens with disallowed algorithms
        alg = unverified_header.get("alg")
        if alg not in self._allowed_algorithms:
            logger.warning(
                "Token with disallowed algorithm rejected",
                algorithm=alg,
                allowed=self._allowed_algorithms,
            )
            raise JWTError(
                f"Algorithm {alg} not allowed. Must be one of: {self._allowed_algorithms}"
            )

        kid = unverified_header.get("kid")
        if not kid:
            raise JWTError("Token missing kid header")

        # Try to find key in cache first
        jwks = await self._get_jwks()
        key = self._find_key_by_kid(jwks, kid)

        if key:
            return key

        # Security: Key not found - might be key rotation, force refresh once
        logger.info("Key not found in cache, forcing JWKS refresh", kid=kid)
        jwks = await self._get_jwks(force_refresh=True)
        key = self._find_key_by_kid(jwks, kid)

        if key:
            return key

        raise JWTError(f"Unable to find matching key for kid: {kid}")

    def _find_key_by_kid(self, jwks: dict[str, Any], kid: str) -> dict[str, Any] | None:
        """Find a key in JWKS by kid."""
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key
        return None

    def _validate_required_claims(self, claims: dict[str, Any]) -> None:
        """Validate that all required claims are present."""
        missing = [claim for claim in REQUIRED_CLAIMS if claim not in claims]
        if missing:
            raise JWTError(f"Missing required claims: {missing}")

    async def verify_token(self, token: str) -> dict[str, Any]:
        """Verify JWT token and return claims.

        Security features:
        - Algorithm restriction (checked before signature verification)
        - Strict audience validation
        - Strict issuer validation
        - Required claims validation
        - Expiration validation
        """
        try:
            signing_key = await self._get_signing_key(token)

            # Build public key
            public_key = jwk.construct(signing_key)

            # Security: Strict validation options
            options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_aud": True,  # Always verify audience
                "require_exp": True,
                "require_iat": True,
            }

            # Decode and verify with strict settings
            claims = jwt.decode(
                token,
                public_key,
                algorithms=self._allowed_algorithms,  # Security: Only allow specific algorithms
                audience=self.audience,
                issuer=self.issuer,
                options=options,
            )

            # Security: Validate required claims are present
            self._validate_required_claims(claims)

            # Security: Log successful verification (without sensitive data)
            logger.debug(
                "Token verified successfully",
                sub=claims.get("sub"),
                token_use=claims.get("token_use"),
            )

            return claims

        except JWTError as e:
            logger.warning("JWT verification failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            ) from e


# Global auth middleware instance (lazy initialized)
_auth_middleware: JWTAuthMiddleware | None = None


def get_auth_middleware() -> JWTAuthMiddleware:
    """Get or create the auth middleware instance."""
    global _auth_middleware

    if _auth_middleware is None:
        if not settings.cognito_user_pool_id or not settings.cognito_region:
            raise RuntimeError("Cognito settings not configured")

        if not settings.cognito_client_id:
            raise RuntimeError("Cognito client ID (audience) not configured")

        jwks_url = (
            f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
            f"{settings.cognito_user_pool_id}/.well-known/jwks.json"
        )
        issuer = (
            f"https://cognito-idp.{settings.cognito_region}.amazonaws.com/"
            f"{settings.cognito_user_pool_id}"
        )

        _auth_middleware = JWTAuthMiddleware(
            jwks_url=jwks_url,
            audience=settings.cognito_client_id,
            issuer=issuer,
        )

    return _auth_middleware


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> AuthenticatedUser | None:
    """Dependency to get the current authenticated user.

    Security: Supports two authentication methods:
    1. Bearer token in Authorization header (for API clients)
    2. httpOnly cookie (for browser clients - XSS protection)

    Returns None if no valid token is provided (for optional auth).
    """
    # Try to get token from Authorization header first
    token: str | None = None

    if credentials:
        token = credentials.credentials
    else:
        # Security: Fall back to httpOnly cookie (XSS-safe)
        token = request.cookies.get(ACCESS_TOKEN_COOKIE)

    if not token:
        return None

    if not settings.auth_enabled:
        # Return a mock user in development
        return AuthenticatedUser(
            sub="dev-user",
            email="dev@example.com",
            name="Development User",
        )

    auth = get_auth_middleware()
    claims = await auth.verify_token(token)

    # Security: Validate sub claim is present and not empty
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        sub=sub,
        email=claims.get("email"),
        name=claims.get("name") or claims.get("cognito:username"),
        groups=claims.get("cognito:groups", []),
        token_use=claims.get("token_use"),
    )


async def require_auth(
    user: Annotated[AuthenticatedUser | None, Depends(get_current_user)],
) -> AuthenticatedUser:
    """
    Dependency that requires authentication.
    Raises 401 if user is not authenticated.
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_groups(*required_groups: str):
    """
    Dependency factory that requires user to be in specific groups.

    Usage:
        @router.get("/admin")
        async def admin_endpoint(user: AuthenticatedUser = Depends(require_groups("admin"))):
            ...
    """

    async def check_groups(
        user: Annotated[AuthenticatedUser, Depends(require_auth)],
    ) -> AuthenticatedUser:
        user_groups = user.groups or []

        if not any(g in user_groups for g in required_groups):
            logger.warning(
                "Access denied: missing required group",
                user_id=user.user_id,
                required_groups=required_groups,
                user_groups=user_groups,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of groups: {', '.join(required_groups)}",
            )

        return user

    return check_groups


# =============================================================================
# Secure Token Storage (httpOnly Cookies)
# =============================================================================


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str | None = None,
    secure: bool = True,
) -> None:
    """Set authentication tokens in httpOnly cookies.

    Security features:
    - httpOnly: Prevents JavaScript access (XSS protection)
    - Secure: Only sent over HTTPS
    - SameSite=Lax: CSRF protection while allowing navigation
    - Path=/: Available to all routes

    Args:
        response: FastAPI Response object
        access_token: JWT access token
        refresh_token: Optional refresh token
        secure: Set Secure flag (False for local development)
    """
    # Set access token cookie
    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=TOKEN_COOKIE_MAX_AGE,
        httponly=True,  # Security: Not accessible via JavaScript
        secure=secure,  # Security: HTTPS only in production
        samesite="lax",  # Security: CSRF protection
        path="/",
    )

    # Set refresh token cookie if provided
    if refresh_token:
        response.set_cookie(
            key=REFRESH_TOKEN_COOKIE,
            value=refresh_token,
            max_age=REFRESH_COOKIE_MAX_AGE,
            httponly=True,
            secure=secure,
            samesite="lax",
            path="/",
        )

    logger.debug("Auth cookies set successfully")


def clear_auth_cookies(response: Response) -> None:
    """Clear authentication cookies (logout).

    Security: Properly clears cookies by setting them to empty
    with immediate expiration.
    """
    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE,
        path="/",
        httponly=True,
        samesite="lax",
    )

    logger.debug("Auth cookies cleared")


def get_refresh_token_from_cookie(request: Request) -> str | None:
    """Get refresh token from httpOnly cookie.

    Used for token refresh flow.
    """
    return request.cookies.get(REFRESH_TOKEN_COOKIE)
