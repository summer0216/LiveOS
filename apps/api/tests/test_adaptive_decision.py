import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from app.core.ai_client import ai_client
from app.models.decision_memory import DecisionMemoryCategory
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.runtime.adaptive_decision import adaptive_decision
from app.runtime.decision import build_decision_prompt
from app.runtime.living_model import LivingModel, LivingModelProfile
from app.runtime.memory_context import DecisionMemoryContextItem
from app.schemas.decision import DecisionInput, PropertyDecisionInput
from app.schemas.decision_context import DecisionContext
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from tests.ids import uuid_for

CONVERSATION_IDS = (
    uuid_for("adaptive-runtime"),
    uuid_for("adaptive-failure"),
)


@pytest.fixture(autouse=True)
def clean_adaptive_data() -> Iterator[None]:
    for conversation_id in CONVERSATION_IDS:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)

    yield

    for conversation_id in CONVERSATION_IDS:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)


def memory_item(content: str) -> DecisionMemoryContextItem:
    return DecisionMemoryContextItem(
        category=DecisionMemoryCategory.PREFERENCE,
        content=content,
        confidence=0.85,
        evidence_count=3,
        updated_at=datetime.now(UTC),
    )


def decision_input(
    *,
    budget: int = 7000,
    memory_content: str = "用户持续偏好较短通勤。",
) -> DecisionInput:
    return DecisionInput(
        living_model=LivingModel(
            conversation_id="adaptive-prompt",
            profile=LivingModelProfile(
                budget=budget,
                commute_minutes=25,
                family_size=2,
            ),
            decision_memory=[memory_item(memory_content)],
        ),
        properties=[
            PropertyDecisionInput(
                id="property-a",
                title="当前候选",
                rent=6800,
                commute_minutes=20,
            ),
        ],
    )


def empty_context() -> DecisionContext:
    return DecisionContext(
        conversation_id="adaptive-prompt",
        recent_decisions=[],
    )


def prepare_runtime(conversation_id: str) -> Property:
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(
            budget=7000,
            commute_minutes=25,
            preferred_city="深圳",
        ),
        latest_insights=[],
    )
    return property_manager.create(
        conversation_id,
        Property(
            title="当前候选",
            district="南山",
            rent=6800,
            commute_minutes=20,
            pet_friendly=True,
        ),
    )


def ready_json(property_id: str) -> str:
    return json.dumps(
        {
            "status": "ready",
            "summary": "当前候选符合最新预算与通勤要求。",
            "best_property_id": property_id,
            "reasons": [
                {
                    "title": "适应当前要求",
                    "description": "以当前预算和通勤要求为最高优先级。",
                },
            ],
            "trade_offs": [],
            "confidence": 0.82,
            "decision_gap": "当前候选是否仍符合最新预算与通勤要求。",
        },
        ensure_ascii=False,
    )


def test_adaptive_prompt_supports_budget_and_living_model_changes() -> None:
    prompt = build_decision_prompt(decision_input(budget=7000), empty_context())

    assert "ADAPTIVE DECISION:" in prompt
    assert '"budget": 7000' in prompt
    assert "budget" in prompt
    assert "family structure" in prompt
    assert "candidate weighting" in prompt


def test_evolved_preference_can_adapt_strategy_without_overriding_facts() -> None:
    prompt = build_decision_prompt(
        decision_input(memory_content="用户持续偏好更短通勤。"),
        empty_context(),
    )

    assert "用户持续偏好更短通勤。" in prompt
    assert "Evolved Decision Memory is available" in prompt
    assert "Never modify current facts" in prompt
    assert "Never create a preference" in prompt


def test_adaptive_priority_is_explicit() -> None:
    guidance = adaptive_decision.build(
        decision_input().living_model,
        empty_context(),
    )

    assert guidance is not None
    assert (
        "Current Facts > Living Model > Memory Evolution > Decision History" in guidance
    )


def test_no_memory_does_not_claim_learning_changed_decision() -> None:
    living_model = LivingModel(
        conversation_id="adaptive-empty",
        profile=LivingModelProfile(budget=6000),
        decision_memory=[],
    )

    guidance = adaptive_decision.build(living_model, empty_context())

    assert guidance is not None
    assert "No evolved Decision Memory is available" in guidance
    assert "Do not claim that past learning changed" in guidance


def test_adaptive_context_is_conversation_isolated() -> None:
    prompt_a = build_decision_prompt(
        decision_input(memory_content="MEMORY_ONLY_FOR_A"),
        DecisionContext(conversation_id="conversation-a"),
    )
    prompt_b = build_decision_prompt(
        decision_input(memory_content="MEMORY_ONLY_FOR_B"),
        DecisionContext(conversation_id="conversation-b"),
    )

    assert "MEMORY_ONLY_FOR_A" in prompt_a
    assert "MEMORY_ONLY_FOR_B" not in prompt_a
    assert "MEMORY_ONLY_FOR_B" in prompt_b
    assert "MEMORY_ONLY_FOR_A" not in prompt_b


def test_adaptive_failure_omits_layer_and_keeps_decision_intelligence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(
        _living_model: LivingModel,
        _context: DecisionContext,
    ) -> None:
        raise RuntimeError("adaptive context unavailable")

    monkeypatch.setattr(adaptive_decision, "_build_context", fail)

    prompt = build_decision_prompt(decision_input(), empty_context())

    assert "ADAPTIVE DECISION:" not in prompt
    assert "DECISION REASONING:" in prompt


def test_runtime_uses_adaptive_layer_with_one_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("adaptive-runtime")
    property_ = prepare_runtime(conversation_id)
    assert property_.id is not None
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return ready_json(property_.id)

    monkeypatch.setattr(ai_client, "generate_json", generate)

    result = decision_service.generate(conversation_id)

    assert result.status == "ready"
    assert len(prompts) == 1
    assert "ADAPTIVE DECISION:" in prompts[0]


def test_adaptive_failure_still_generates_decision_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("adaptive-failure")
    property_ = prepare_runtime(conversation_id)
    assert property_.id is not None
    call_count = 0

    def fail(
        _living_model: LivingModel,
        _context: DecisionContext,
    ) -> None:
        raise RuntimeError("adaptive context unavailable")

    def generate(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        assert "ADAPTIVE DECISION:" not in prompt
        assert "DECISION REASONING:" in prompt
        return ready_json(property_.id)

    monkeypatch.setattr(adaptive_decision, "_build_context", fail)
    monkeypatch.setattr(ai_client, "generate_json", generate)

    result = decision_service.generate(conversation_id)

    assert result.status == "ready"
    assert call_count == 1
