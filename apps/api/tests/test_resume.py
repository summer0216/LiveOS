from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb

from app.api.ownership import COOKIE_NAME
from app.main import app
from app.models.profile_patch import LivingProfilePatch
from app.schemas.decision import DecisionReason, DecisionResult, DecisionTradeOff
from app.services.conversation_manager import conversation_manager
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.profile_manager import profile_manager
from app.stores.runtime import database


def owned_client(owner_id: str | None = None) -> tuple[TestClient, str]:
    client = TestClient(app)
    resolved_owner_id = owner_id or str(uuid4())
    client.cookies.set(COOKIE_NAME, resolved_owner_id)
    return client, resolved_owner_id


def create_conversation(owner_id: str, conversation_id: str) -> None:
    conversation_manager.get_or_create(conversation_id, owner_id)


def set_activity(conversation_id: str, updated_at: datetime) -> None:
    with database.connect() as connection:
        connection.execute(
            "UPDATE conversations SET updated_at = %s WHERE id = %s",
            (updated_at, conversation_id),
        )


def save_ready(
    conversation_id: str,
    label: str,
    *,
    with_next: bool = True,
) -> None:
    summary = f"{label} Decision"
    if with_next:
        summary += f" 下一步：执行 {label} NEXT。"
    decision_record_service.save(
        conversation_id,
        DecisionResult(
            status="ready",
            summary=summary,
            best_property_id=str(uuid4()),
            reasons=[DecisionReason(title=f"{label}依据", description=label)],
            trade_offs=[
                DecisionTradeOff(title=f"{label}取舍", description=label)
            ],
            confidence=0.8,
        ),
    )


def test_empty_owner_keeps_normal_entry_without_creating_conversation() -> None:
    client, owner_id = owned_client()

    response = client.get("/api/resume")

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": None,
        "profile": None,
        "decision": None,
        "action_progress": None,
    }
    with database.connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) AS count FROM conversations WHERE anonymous_user_id = %s",
            (owner_id,),
        ).fetchone()
    assert count is not None
    assert count["count"] == 0


def test_understanding_only_conversation_is_resumable() -> None:
    client, owner_id = owned_client()
    conversation_id = str(uuid4())
    create_conversation(owner_id, conversation_id)
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(work_location="南山区", budget=6000),
        [],
    )

    response = client.get("/api/resume")

    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation_id"] == conversation_id
    assert payload["profile"]["work_location"] == "南山区"
    assert payload["profile"]["budget"] == 6000
    assert payload["decision"] is None


def test_most_recent_eligible_conversation_restores_only_its_decision() -> None:
    client, owner_id = owned_client()
    conversation_a = str(uuid4())
    conversation_b = str(uuid4())
    other_conversation = str(uuid4())
    create_conversation(owner_id, conversation_a)
    create_conversation(owner_id, conversation_b)
    other_client, other_owner_id = owned_client()
    create_conversation(other_owner_id, other_conversation)
    save_ready(conversation_a, "A")
    save_ready(conversation_b, "B")
    save_ready(other_conversation, "OTHER")
    now = datetime.now(UTC)
    set_activity(conversation_a, now - timedelta(minutes=2))
    set_activity(conversation_b, now - timedelta(minutes=1))
    set_activity(other_conversation, now)

    response = client.get("/api/resume")
    other_response = other_client.get("/api/resume")

    assert response.status_code == 200
    payload = response.json()
    assert payload["conversation_id"] == conversation_b
    assert payload["decision"]["summary"] == "B Decision 下一步：执行 B NEXT。"
    assert payload["decision"]["reasons"][0]["description"] == "B"
    assert payload["decision"]["trade_offs"][0]["description"] == "B"
    assert "A" not in payload["decision"]["summary"]
    assert "OTHER" not in payload["decision"]["summary"]
    assert other_response.json()["conversation_id"] == other_conversation


def test_known_conversation_uses_exact_conversation_scope() -> None:
    client, owner_id = owned_client()
    conversation_a = str(uuid4())
    conversation_b = str(uuid4())
    create_conversation(owner_id, conversation_a)
    create_conversation(owner_id, conversation_b)
    save_ready(conversation_a, "A")
    save_ready(conversation_b, "B")

    response = client.get(
        "/api/resume",
        params={"conversation_id": conversation_a},
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == conversation_a
    assert response.json()["decision"]["summary"].startswith("A Decision")


def test_resume_rejects_conversation_owned_by_another_owner() -> None:
    owner_client, owner_id = owned_client()
    other_client, _other_owner_id = owned_client()
    conversation_id = str(uuid4())
    create_conversation(owner_id, conversation_id)

    response = other_client.get(
        "/api/resume",
        params={"conversation_id": conversation_id},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Conversation not found."
    assert owner_client.get(
        "/api/resume",
        params={"conversation_id": conversation_id},
    ).status_code == 200


def test_legacy_record_without_conversation_scope_is_not_resumable() -> None:
    client, owner_id = owned_client()
    conversation_id = str(uuid4())
    create_conversation(owner_id, conversation_id)
    timestamp = datetime.now(UTC)
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO decision_records(
                id, owner_id, conversation_id, created_at, summary, best_property_id,
                reasons_json, trade_offs_json, confidence
            )
            VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid4()),
                owner_id,
                timestamp,
                "Legacy Decision 下一步：Legacy NEXT。",
                str(uuid4()),
                Jsonb([{"title": "Legacy", "description": "Legacy"}]),
                Jsonb([{"title": "Legacy", "description": "Legacy"}]),
                0.7,
            ),
        )

    response = client.get("/api/resume")

    assert response.status_code == 200
    assert response.json()["conversation_id"] is None
    assert response.json()["decision"] is None


def test_missing_next_does_not_block_decision_and_tradeoff_resume() -> None:
    client, owner_id = owned_client()
    conversation_id = str(uuid4())
    create_conversation(owner_id, conversation_id)
    save_ready(conversation_id, "Legacy", with_next=False)

    response = client.get(
        "/api/resume",
        params={"conversation_id": conversation_id},
    )

    decision = response.json()["decision"]
    assert decision["summary"] == "Legacy Decision"
    assert "下一步：" not in decision["summary"]
    assert decision["trade_offs"][0]["description"] == "Legacy"


def test_latest_valid_ready_record_skips_newer_invalid_record() -> None:
    client, owner_id = owned_client()
    conversation_id = str(uuid4())
    create_conversation(owner_id, conversation_id)
    save_ready(conversation_id, "Valid")
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO decision_records(
                id, owner_id, conversation_id, created_at, summary, best_property_id,
                reasons_json, trade_offs_json, confidence
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid4()),
                owner_id,
                conversation_id,
                datetime.now(UTC) + timedelta(seconds=1),
                "Invalid newer record",
                str(uuid4()),
                Jsonb([]),
                Jsonb([]),
                0.7,
            ),
        )

    response = client.get(
        "/api/resume",
        params={"conversation_id": conversation_id},
    )

    assert response.status_code == 200
    assert response.json()["decision"]["summary"].startswith("Valid Decision")


def test_resume_is_read_only_and_does_not_generate_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, owner_id = owned_client()
    conversation_id = str(uuid4())
    create_conversation(owner_id, conversation_id)
    save_ready(conversation_id, "Stable")
    with database.connect() as connection:
        before = connection.execute(
            "SELECT COUNT(*) AS count FROM decision_records WHERE owner_id = %s",
            (owner_id,),
        ).fetchone()
    assert before is not None

    def fail_generate(_conversation_id: str) -> None:
        raise AssertionError("Resume must not generate a Decision.")

    monkeypatch.setattr(decision_service, "generate", fail_generate)

    root_response = client.get("/api/resume")
    known_response = client.get(
        "/api/resume",
        params={"conversation_id": conversation_id},
    )

    assert root_response.status_code == 200
    assert known_response.status_code == 200
    with database.connect() as connection:
        after = connection.execute(
            "SELECT COUNT(*) AS count FROM decision_records WHERE owner_id = %s",
            (owner_id,),
        ).fetchone()
    assert after is not None
    assert after["count"] == before["count"]
