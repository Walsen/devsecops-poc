"""Tests for CSRF middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.presentation.middleware.csrf import CSRFMiddleware


@pytest.fixture
def app_with_csrf():
    """Create a test app with CSRF middleware."""
    app = FastAPI()

    app.add_middleware(
        CSRFMiddleware,
        secret_key="test-secret-key-for-csrf",  # noqa: S106
        secure_cookies=False,  # Allow non-HTTPS in tests
    )

    @app.get("/")
    def root():
        return {"status": "ok"}

    @app.post("/api/data")
    def create_data():
        return {"created": True}

    @app.get("/health")
    def health():
        return {"healthy": True}

    return app


@pytest.fixture
def client(app_with_csrf):
    """Create test client."""
    return TestClient(app_with_csrf)


class TestCSRFMiddleware:
    """Tests for CSRF protection."""

    def test_get_request_sets_csrf_cookie(self, client):
        """GET requests should set CSRF cookie."""
        response = client.get("/")

        assert response.status_code == 200
        assert "csrf_token" in response.cookies

    def test_post_without_csrf_token_fails(self, client):
        """POST without CSRF token should fail."""
        response = client.post("/api/data")

        assert response.status_code == 403
        assert "CSRF" in response.json()["detail"]

    def test_post_with_valid_csrf_token_succeeds(self, client):
        """POST with valid CSRF token should succeed."""
        # First, get a CSRF token via GET
        get_response = client.get("/")
        csrf_token = get_response.cookies.get("csrf_token")

        # Then POST with the token in header
        response = client.post(
            "/api/data",
            headers={"X-CSRF-Token": csrf_token},
            cookies={"csrf_token": csrf_token},
        )

        assert response.status_code == 200
        assert response.json()["created"] is True

    def test_post_with_mismatched_tokens_fails(self, client):
        """POST with mismatched cookie/header tokens should fail."""
        # Get a valid token
        get_response = client.get("/")
        csrf_token = get_response.cookies.get("csrf_token")

        # Send with different header token
        response = client.post(
            "/api/data",
            headers={"X-CSRF-Token": "wrong-token"},
            cookies={"csrf_token": csrf_token},
        )

        assert response.status_code == 403

    def test_exempt_paths_skip_csrf(self, client):
        """Exempt paths should not require CSRF."""
        # Health endpoint is exempt
        response = client.post("/health")

        # Should not fail with 403 (might fail with 405 if POST not allowed)
        assert response.status_code != 403

    def test_csrf_token_rotates_after_post(self, client):
        """CSRF token should rotate after successful POST."""
        # Get initial token
        get_response = client.get("/")
        initial_token = get_response.cookies.get("csrf_token")

        # POST with token
        post_response = client.post(
            "/api/data",
            headers={"X-CSRF-Token": initial_token},
            cookies={"csrf_token": initial_token},
        )

        # Token should be rotated
        new_token = post_response.cookies.get("csrf_token")
        assert new_token is not None
        assert new_token != initial_token


class TestCSRFTokenValidation:
    """Tests for CSRF token validation logic."""

    def test_tampered_token_fails(self, client):
        """Tampered CSRF token should fail validation."""
        # Get a valid token
        get_response = client.get("/")
        csrf_token = get_response.cookies.get("csrf_token")

        # Tamper with the token (change a character)
        tampered = csrf_token[:-1] + ("a" if csrf_token[-1] != "a" else "b")

        response = client.post(
            "/api/data",
            headers={"X-CSRF-Token": tampered},
            cookies={"csrf_token": tampered},
        )

        assert response.status_code == 403
