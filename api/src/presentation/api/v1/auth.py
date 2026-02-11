"""Authentication endpoints for secure token management.

Security: Implements secure token storage using httpOnly cookies
to protect against XSS attacks. Tokens are never exposed to JavaScript.

Flow:
1. Client authenticates with Cognito (OAuth/password)
2. Client sends tokens to /auth/session endpoint
3. Server stores tokens in httpOnly cookies
4. Subsequent requests use cookies automatically
5. Logout clears cookies
"""

import structlog
from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel

from ....config import settings
from ...middleware import (
    clear_auth_cookies,
    get_refresh_token_from_cookie,
    set_auth_cookies,
)

logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["Authentication"])


class TokenRequest(BaseModel):
    """Request body for setting auth session."""

    access_token: str
    refresh_token: str | None = None


class SessionResponse(BaseModel):
    """Response for session operations."""

    success: bool
    message: str


@router.post(
    "/session",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Set authentication session",
    description="Store tokens in secure httpOnly cookies after Cognito authentication.",
)
async def set_session(
    tokens: TokenRequest,
    response: Response,
) -> SessionResponse:
    """Set authentication tokens in httpOnly cookies.

    Security: This endpoint receives tokens from the client after
    Cognito authentication and stores them in httpOnly cookies.
    This protects tokens from XSS attacks since JavaScript cannot
    access httpOnly cookies.

    The client should call this endpoint immediately after receiving
    tokens from Cognito, then discard the tokens from memory.
    """
    set_auth_cookies(
        response=response,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        secure=not settings.debug,
    )

    logger.info("Auth session created")

    return SessionResponse(
        success=True,
        message="Session created successfully",
    )


@router.post(
    "/logout",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout and clear session",
    description="Clear authentication cookies to end the session.",
)
async def logout(response: Response) -> SessionResponse:
    """Clear authentication cookies (logout).

    Security: Properly clears httpOnly cookies to end the session.
    The client should also clear any local state and redirect to login.
    """
    clear_auth_cookies(response)

    logger.info("User logged out")

    return SessionResponse(
        success=True,
        message="Logged out successfully",
    )


@router.get(
    "/session",
    response_model=SessionResponse,
    summary="Check session status",
    description="Check if user has a valid session (cookies present).",
)
async def check_session(request: Request) -> SessionResponse:
    """Check if authentication cookies are present.

    Note: This only checks for cookie presence, not token validity.
    Token validation happens in the auth middleware on protected routes.
    """
    from ...middleware import ACCESS_TOKEN_COOKIE

    has_session = ACCESS_TOKEN_COOKIE in request.cookies

    return SessionResponse(
        success=has_session,
        message="Session active" if has_session else "No active session",
    )


@router.post(
    "/refresh",
    response_model=SessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Use refresh token to get new access token (placeholder).",
)
async def refresh_token(
    request: Request,
    response: Response,
) -> SessionResponse:
    """Refresh access token using refresh token from cookie.

    Note: This is a placeholder. Full implementation requires
    calling Cognito's token endpoint with the refresh token.

    Security: Refresh token is read from httpOnly cookie,
    never exposed to JavaScript.
    """
    refresh_token = get_refresh_token_from_cookie(request)

    if not refresh_token:
        return SessionResponse(
            success=False,
            message="No refresh token available",
        )

    # TODO: Implement Cognito token refresh
    # This would call Cognito's /oauth2/token endpoint with:
    # - grant_type=refresh_token
    # - refresh_token=<refresh_token>
    # - client_id=<cognito_client_id>

    logger.info("Token refresh requested (not implemented)")

    return SessionResponse(
        success=False,
        message="Token refresh not yet implemented",
    )
