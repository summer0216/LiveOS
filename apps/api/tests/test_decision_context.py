import json
from collections.abc import Iterator

import pytest

from app.core.ai_client import ai_client
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.schemas.decision import DecisionReason, DecisionResult
from app.schemas.decision_record import DecisionRecord
from app.services.decision_context_service import decision_context_service
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager

CONVERSATION_IDS = (
    "context-empty",
    "context-one",
    "context-three",
    "context-many",
    "context-isolation-a",
    "context-isolation-b",
    "context-failure",
)


@pytest.fixture(autouse=True)
def clean_context_data() -> Iterator[None]:
    for conversation_id in CONVERSATION_IDS:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)

    yield

    for conversation_id in CONVERSATION_IDS:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)


def ready_decision(
    property_id: str,
    summary: str,
) -> DecisionResult:
    return DecisionResult(
        status="ready",
        summary=summary,
        best_property_id=property_id,
        reasons=[
            DecisionReason(
                title="Context 测试",
                description="用于验证 Decision Context。",
            ),
        ],
        trade_offs=[],
        confidence=0.8,
    )


def save_records(
    conversation_id: str,
    count: int,
) -> None:
    for index in range(count):
        decision_record_service.save(
            conversation_id,
            ready_decision(
                property_id=f"property-{index}",
                summary=f"Decision {index}",
            ),
        )


def prepare_runtime(conversation_id: str) -> Property:
    profile_manager.merge(
        conversation_id=conversation_id,
        patch=LivingProfilePatch(
            work_location="南山科技园",
            budget=6000,
            commute_minutes=30,
            preferred_city="深圳",
            family_size=2,
            has_pet=False,
        ),
        latest_insights=[],
    )
    return property_manager.create(
        conversation_id=conversation_id,
        property_=Property(
            title="Context 测试房源",
            district="南山",
            rent=5800,
            area=65,
            bedrooms=2,
            bathrooms=1,
            commute_minutes=25,
            pet_friendly=True,
        ),
    )


def test_empty_history_returns_empty_context() -> None:
    context = decision_context_service.build_context("context-empty")

    assert context.conversation_id == "context-empty"
    assert context.recent_decisions == []


def test_one_record_returns_one_snapshot() -> None:
    save_records("context-one", 1)

    context = decision_context_service.build_context("context-one")

    assert len(context.recent_decisions) == 1
    assert context.recent_decisions[0].summary == "Decision 0"


def test_more_than_three_records_returns_latest_three() -> None:
    save_records("context-many", 5)

    context = decision_context_service.build_context("context-many")

    assert len(context.recent_decisions) == 3
    assert [
        record.summary
        for record in context.recent_decisions
    ] == [
        "Decision 4",
        "Decision 3",
        "Decision 2",
    ]


def test_three_records_returns_all_three() -> None:
    save_records("context-three", 3)

    context = decision_context_service.build_context("context-three")

    assert [
        record.summary
        for record in context.recent_decisions
    ] == [
        "Decision 2",
        "Decision 1",
        "Decision 0",
    ]


def test_context_is_isolated_by_conversation() -> None:
    save_records("context-isolation-a", 2)
    save_records("context-isolation-b", 1)

    context_a = decision_context_service.build_context(
        "context-isolation-a",
    )
    context_b = decision_context_service.build_context(
        "context-isolation-b",
    )

    assert len(context_a.recent_decisions) == 2
    assert len(context_b.recent_decisions) == 1
    assert {
        record.conversation_id
        for record in context_a.recent_decisions
    } == {"context-isolation-a"}
    assert {
        record.conversation_id
        for record in context_b.recent_decisions
    } == {"context-isolation-b"}


def test_history_failure_returns_empty_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_history(_conversation_id: str) -> list[DecisionRecord]:
        raise RuntimeError("History unavailable")

    monkeypatch.setattr(
        decision_record_service,
        "list_by_conversation",
        fail_history,
    )

    context = decision_context_service.build_context("context-failure")

    assert context.recent_decisions == []


def test_history_failure_does_not_stop_decision_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = "context-failure"
    property_ = prepare_runtime(conversation_id)
    assert property_.id is not None

    def fail_history(_conversation_id: str) -> list[DecisionRecord]:
        raise RuntimeError("History unavailable")

    monkeypatch.setattr(
        decision_record_service,
        "list_by_conversation",
        fail_history,
    )
    monkeypatch.setattr(
        ai_client,
        "generate_json",
        lambda _prompt: json.dumps(
            {
                "status": "ready",
                "summary": "Context 失败不影响当前决策。",
                "best_property_id": property_.id,
                "reasons": [
                    {
                        "title": "Context 降级",
                        "description": "History 失败不影响当前决策。",
                    },
                ],
                "trade_offs": [],
                "confidence": 0.8,
            },
            ensure_ascii=False,
        ),
    )

    result = decision_service.generate(conversation_id)

    assert result.status == "ready"
    assert result.best_property_id == property_.id
