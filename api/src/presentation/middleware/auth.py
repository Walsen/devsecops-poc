import time
from dataclasses import dataclass
from typing import Annotated

import httpx
import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt

from ...config import settings

logger = structlog.get_logger()

security = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    """Represents an authenticated user from JWT claims."""

    sub: str  # User ID
    email: str | None = None
    name: str | None = None
    groups: list[str] | None = None

    @property
    def user_id(self) -> str:
        return self.sub


class JWTAuthMiddleware:
    """JWT authentication using Cognito JWKS."""

    def __init__(
        self,
        jwks_url: str,
        audience: str | None = None,
        issuer: str | None = None,
    ):
        self.jwks_url = jwks_url
        self.audience = audience
        self.issuer = issuer
        self._jwks_cache: dict | None = None
        self._jwks_cache_time: float = 0
        self._cache_ttl = 3600  # 1 hour

    async def _get_jwks(self) -> dict:
        """Fetch and cache JWKS from Cognito."""
        now = time.time()

        if self._jwks_cache and (now - self._jwks_cache_time) < self._cache_ttl:
            return self._jwks_cache

        async with httpx.AsyncClient() as client:
            response = await client.get(self.jwks_url)
            response.raise_for_status()
            self._jwks_cache = response.json()
            self._jwks_cache_time = now

        return self._jwks_cache

    async def _get_signing_key(self, token: str) -> dict:
        """Get the signing key for a token from JWKS."""
        jwks = await self._get_jwks()

        # Get the kid from token header
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        if not kid:
            raise JWTError("Token missing kid header")

        # Find matching key
        for key in jwks.get("keys", []):
            if key.get("kid") == kid:
                return key

        raise JWTError(f"Unable to find matching key for kid: {kid}")

    async def verify_token(self, token: str) -> dict:
        """Verify JWT token and return claims."""
        try:
            signing_key = await self._get_signing_key(token)

            # Build public key
            public_key = jwk.construct(signing_key)

            # Decode and verify
            options = {
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": self.audience is not None,
                "verify_iss": self.issuer is not None,
            }

            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self.audience,
                issuer=self.issuer,
                options=options,
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
    """
    Dependency to get the current authenticated user.
    Returns None if no valid token is provided (for optional auth).
    """
    if not credentials:
        return None

    if not settings.auth_enabled:
        # Return a mock user in development
        return AuthenticatedUser(
            sub="dev-user",
            email="dev@example.com",
            name="Development User",
        )

    auth = get_auth_middleware()
    claims = await auth.verify_token(credentials.credentials)

    return AuthenticatedUser(
        sub=claims.get("sub"),
        email=claims.get("email"),
        name=claims.get("name") or claims.get("cognito:username"),
        groups=claims.get("cognito:groups", []),
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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of groups: {', '.join(required_groups)}",
            )

        return user

    return check_groups
