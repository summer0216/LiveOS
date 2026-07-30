from collections.abc import Iterator
from typing import Never

import pytest
from fastapi.testclient import TestClient

from app.core.ai_client import ai_client
from app.main import app
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.schemas.decision import DecisionResult
from app.schemas.decision_record import DecisionRecord
from app.services.conversation_manager import conversation_manager
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager

client = TestClient(app)

CONVERSATION_IDS = (
    "history-empty",
    "history-single",
    "history-multiple",
    "history-waiting",
    "history-detail",
    "history-isolation-a",
    "history-isolation-b",
    "history-snapshot",
    "history-store-error",
)


@pytest.fixture(autouse=True)
def clean_history_data() -> Iterator[None]:
    for conversation_id in CONVERSATION_IDS:
        conversation_manager.delete(conversation_id)
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)

    yield

    for conversation_id in CONVERSATION_IDS:
        conversation_manager.delete(conversation_id)
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)


def create_conversation(conversation_id: str) -> None:
    conversation_manager.get_or_create(conversation_id)


def ready_decision(
    property_id: str,
    summary: str,
) -> DecisionResult:
    return DecisionResult(
        status="ready",
        summary=summary,
        best_property_id=property_id,
        reasons=[
            {
                "title": "预算匹配",
                "description": "月租处于保存 Decision 时的预算范围内。",
            },
        ],
        trade_offs=[
            {
                "title": "面积取舍",
                "description": "保存时记录的面积取舍。",
            },
        ],
        confidence=0.86,
    )


def save_record(
    conversation_id: str,
    summary: str,
    *,
    property_id: str = "property-history",
) -> DecisionRecord:
    return decision_record_service.save(
        conversation_id=conversation_id,
        decision=ready_decision(property_id, summary),
    )


def history_path(conversation_id: str) -> str:
    return f"/api/conversations/{conversation_id}/decisions/history"


def test_empty_history_returns_200_and_unknown_conversation_returns_404() -> None:
    conversation_id = "history-empty"
    create_conversation(conversation_id)

    response = client.get(history_path(conversation_id))
    unknown_response = client.get(
        history_path("history-unknown"),
    )

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": conversation_id,
        "items": [],
        "total": 0,
    }
    assert unknown_response.status_code == 404


def test_single_record_list_returns_saved_snapshot() -> None:
    conversation_id = "history-single"
    create_conversation(conversation_id)
    record = save_record(
        conversation_id,
        "单条历史快照",
        property_id="property-single",
    )

    response = client.get(history_path(conversation_id))
    payload = response.json()

    assert response.status_code == 200
    assert payload["total"] == 1
    assert payload["items"][0]["id"] == record.id
    assert payload["items"][0]["summary"] == "单条历史快照"
    assert payload["items"][0]["best_property_id"] == "property-single"


def test_multiple_records_are_returned_in_descending_time_order() -> None:
    conversation_id = "history-multiple"
    create_conversation(conversation_id)
    first = save_record(conversation_id, "第一次 Decision")
    second = save_record(conversation_id, "第二次 Decision")
    third = save_record(conversation_id, "第三次 Decision")

    response = client.get(history_path(conversation_id))
    payload = response.json()

    assert response.status_code == 200
    assert payload["total"] == 3
    assert [item["id"] for item in payload["items"]] == [
        third.id,
        second.id,
        first.id,
    ]
    assert [
        item["created_at"]
        for item in payload["items"]
    ] == sorted(
        [item["created_at"] for item in payload["items"]],
        reverse=True,
    )


def test_waiting_decision_does_not_add_history() -> None:
    conversation_id = "history-waiting"
    create_conversation(conversation_id)

    result = decision_service.generate(conversation_id)
    response = client.get(history_path(conversation_id))

    assert result.status == "waiting"
    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_record_detail_and_missing_record() -> None:
    conversation_id = "history-detail"
    create_conversation(conversation_id)
    record = save_record(conversation_id, "详情快照")

    response = client.get(
        f"{history_path(conversation_id)}/{record.id}",
    )
    missing_response = client.get(
        f"{history_path(conversation_id)}/missing-record",
    )

    assert response.status_code == 200
    assert response.json()["id"] == record.id
    assert response.json()["summary"] == "详情快照"
    assert missing_response.status_code == 404
    assert missing_response.json()["detail"] == "Decision record not found."


def test_history_isolated_by_conversation() -> None:
    conversation_a = "history-isolation-a"
    conversation_b = "history-isolation-b"
    create_conversation(conversation_a)
    create_conversation(conversation_b)
    record_a = save_record(
        conversation_a,
        "A 的历史",
        property_id="property-a",
    )
    record_b = save_record(
        conversation_b,
        "B 的历史",
        property_id="property-b",
    )

    list_a = client.get(history_path(conversation_a)).json()
    cross_detail = client.get(
        f"{history_path(conversation_b)}/{record_a.id}",
    )

    assert list_a["total"] == 1
    assert list_a["items"][0]["id"] == record_a.id
    assert list_a["items"][0]["id"] != record_b.id
    assert cross_detail.status_code == 404
    assert cross_detail.json()["detail"] == "Decision record not found."


def test_snapshot_survives_profile_change_and_property_deletion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = "history-snapshot"
    create_conversation(conversation_id)
    profile_manager.merge(
        conversation_id=conversation_id,
        patch=LivingProfilePatch(budget=6000),
        latest_insights=[],
    )
    property_ = property_manager.create(
        conversation_id=conversation_id,
        property_=Property(
            title="保存时房源",
            rent=5800,
        ),
    )
    assert property_.id is not None
    record = save_record(
        conversation_id,
        "保存时的 Decision 快照",
        property_id=property_.id,
    )

    profile_manager.merge(
        conversation_id=conversation_id,
        patch=LivingProfilePatch(budget=9000),
        latest_insights=[],
    )
    property_.title = "修改后的房源"
    property_.rent = 8800
    assert property_manager.delete(property_.id)

    def unexpected_ai_call(_prompt: str) -> str:
        raise AssertionError("History query must not call AI.")

    monkeypatch.setattr(ai_client, "generate_json", unexpected_ai_call)

    response = client.get(
        f"{history_path(conversation_id)}/{record.id}",
    )

    assert response.status_code == 200
    assert response.json()["summary"] == "保存时的 Decision 快照"
    assert response.json()["best_property_id"] == property_.id
    assert response.json()["confidence"] == 0.86


def test_store_read_failure_returns_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = "history-store-error"
    create_conversation(conversation_id)

    def fail_read(_conversation_id: str) -> Never:
        raise RuntimeError("Record store unavailable")

    monkeypatch.setattr(
        decision_record_service,
        "list_by_conversation",
        fail_read,
    )

    response = client.get(history_path(conversation_id))

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "Decision history could not be loaded."
    )
