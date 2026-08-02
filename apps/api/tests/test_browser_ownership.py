import pytest
from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.api.ownership import COOKIE_NAME
from app.core.config import settings
from app.main import app
from app.services.conversation_manager import conversation_manager
from app.services.property_manager import property_manager
from tests.ids import uuid_for


def test_cors_allows_explicit_development_origins_with_credentials() -> None:
    client = TestClient(app)

    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        response = client.options(
            "/api/properties",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"


def test_cors_does_not_allow_unknown_origin() -> None:
    response = TestClient(app).options(
        "/api/properties",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_health_check_verifies_postgresql_and_schema() -> None:
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": "ok",
        "schema": "ready",
    }


def test_anonymous_cookie_is_http_only_lax_and_secure_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("browser-cookie-production")
    conversation_manager.delete(conversation_id)
    property_manager.delete_conversation(conversation_id)
    monkeypatch.setattr(settings, "APP_ENV", "production")

    response = TestClient(app).post(
        "/api/properties",
        json={"conversation_id": conversation_id, "title": "Cookie validation"},
    )
    cookie = response.headers["set-cookie"]

    assert response.status_code == 201
    assert cookie.startswith(f"{COOKIE_NAME}=")
    assert "HttpOnly" in cookie
    assert "Path=/" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" in cookie

    property_manager.delete_conversation(conversation_id)
    conversation_manager.delete(conversation_id)


def test_streaming_response_sets_cookie_and_preserves_owner_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("browser-stream-owner")
    conversation_manager.delete(conversation_id)

    def stream_reply(*, conversation_id: str, message: str):
        del conversation_id, message
        yield "ok"

    monkeypatch.setattr(chat_api.chat_service, "chat_stream", stream_reply)
    owner_client = TestClient(app)
    other_client = TestClient(app)

    stream_response = owner_client.post(
        "/api/chat/stream",
        json={"conversation_id": conversation_id, "message": "hello"},
    )
    owner_response = owner_client.get(
        "/api/properties",
        params={"conversation_id": conversation_id},
    )
    other_response = other_client.get(
        "/api/properties",
        params={"conversation_id": conversation_id},
    )

    assert stream_response.status_code == 200
    assert stream_response.headers["set-cookie"].startswith(f"{COOKIE_NAME}=")
    assert owner_response.status_code == 200
    assert other_response.status_code == 404

    conversation_manager.delete(conversation_id)
