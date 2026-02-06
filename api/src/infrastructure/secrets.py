"""Secrets Manager client for runtime secret fetching.

Security: Fetches secrets at runtime instead of storing in environment variables.
This prevents secrets from being exposed in:
- Lambda environment variable dumps
- Container inspection
- Process environment listings
- Log files
"""

import json
from functools import lru_cache
from typing import Any

import boto3
import structlog
from botocore.exceptions import ClientError

logger = structlog.get_logger()

# Cache TTL for secrets (in seconds)
_SECRET_CACHE_TTL = 300  # 5 minutes


class SecretsManager:
    """
    Client for AWS Secrets Manager with caching.

    Security: Fetches secrets at runtime with caching to balance
    security (no env vars) with performance (minimal API calls).
    """

    def __init__(self, region_name: str | None = None) -> None:
        """
        Initialize Secrets Manager client.

        Args:
            region_name: AWS region. If None, uses default from environment.
        """
        self._client = boto3.client("secretsmanager", region_name=region_name)
        self._cache: dict[str, tuple[Any, float]] = {}

    def get_secret(self, secret_id: str, use_cache: bool = True) -> dict[str, Any]:
        """
        Fetch a secret from Secrets Manager.

        Args:
            secret_id: The ARN or name of the secret
            use_cache: Whether to use cached value if available

        Returns:
            Parsed JSON secret value as dictionary

        Raises:
            SecretNotFoundError: If secret doesn't exist
            SecretAccessDeniedError: If access is denied
        """
        import time

        # Check cache
        if use_cache and secret_id in self._cache:
            value, cached_at = self._cache[secret_id]
            if time.time() - cached_at < _SECRET_CACHE_TTL:
                logger.debug("Using cached secret", secret_id=secret_id)
                return value

        try:
            response = self._client.get_secret_value(SecretId=secret_id)

            # Parse secret value
            if "SecretString" in response:
                secret_value = json.loads(response["SecretString"])
            else:
                # Binary secret - decode and parse
                import base64

                secret_value = json.loads(
                    base64.b64decode(response["SecretBinary"]).decode("utf-8")
                )

            # Cache the value
            self._cache[secret_id] = (secret_value, time.time())

            logger.info("Secret fetched successfully", secret_id=secret_id)
            return secret_value

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")

            if error_code == "ResourceNotFoundException":
                logger.error("Secret not found", secret_id=secret_id)
                raise SecretNotFoundError(f"Secret not found: {secret_id}") from e

            if error_code in ("AccessDeniedException", "UnauthorizedAccess"):
                logger.error("Access denied to secret", secret_id=secret_id)
                raise SecretAccessDeniedError(f"Access denied: {secret_id}") from e

            logger.error(
                "Failed to fetch secret",
                secret_id=secret_id,
                error_code=error_code,
                error=str(e),
            )
            raise

    def get_secret_value(self, secret_id: str, key: str, use_cache: bool = True) -> str:
        """
        Fetch a specific key from a secret.

        Args:
            secret_id: The ARN or name of the secret
            key: The key within the secret JSON
            use_cache: Whether to use cached value

        Returns:
            The value for the specified key

        Raises:
            KeyError: If key doesn't exist in secret
        """
        secret = self.get_secret(secret_id, use_cache)
        if key not in secret:
            raise KeyError(f"Key '{key}' not found in secret '{secret_id}'")
        return secret[key]

    def clear_cache(self, secret_id: str | None = None) -> None:
        """
        Clear cached secrets.

        Args:
            secret_id: Specific secret to clear, or None to clear all
        """
        if secret_id:
            self._cache.pop(secret_id, None)
        else:
            self._cache.clear()
        logger.info("Secret cache cleared", secret_id=secret_id or "all")


class SecretNotFoundError(Exception):
    """Raised when a secret is not found."""

    pass


class SecretAccessDeniedError(Exception):
    """Raised when access to a secret is denied."""

    pass


# Global instance (lazy initialized)
_secrets_manager: SecretsManager | None = None


def get_secrets_manager(region_name: str | None = None) -> SecretsManager:
    """Get or create the global SecretsManager instance."""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager(region_name)
    return _secrets_manager


@lru_cache(maxsize=32)
def get_oauth_credentials(provider: str, region_name: str | None = None) -> dict[str, str]:
    """
    Get OAuth credentials for a provider.

    Security: Fetches from Secrets Manager at runtime.

    Args:
        provider: OAuth provider name (google, github, linkedin)
        region_name: AWS region

    Returns:
        Dictionary with client_id and client_secret
    """
    secret_id = f"omnichannel/oauth/{provider.lower()}"
    sm = get_secrets_manager(region_name)
    return sm.get_secret(secret_id)


@lru_cache(maxsize=32)
def get_social_api_credentials(platform: str, region_name: str | None = None) -> dict[str, str]:
    """
    Get social media API credentials for a platform.

    Security: Fetches from Secrets Manager at runtime.

    Args:
        platform: Social platform name (facebook, instagram, linkedin, whatsapp)
        region_name: AWS region

    Returns:
        Dictionary with API credentials
    """
    secret_id = f"omnichannel/social/{platform.lower()}"
    sm = get_secrets_manager(region_name)
    return sm.get_secret(secret_id)
