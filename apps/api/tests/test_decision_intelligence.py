import json
from collections.abc import Iterator

import pytest

from app.core.ai_client import ai_client
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.runtime.decision import build_decision_prompt
from app.runtime.decision_intelligence import (
    FALLBACK_DECISION_REASONING,
    decision_intelligence,
)
from app.runtime.living_model import LivingModel, LivingModelProfile
from app.schemas.decision import DecisionInput, PropertyDecisionInput
from app.schemas.decision_context import DecisionContext
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager

CONVERSATION_IDS = (
    "decision-intelligence-runtime",
    "decision-intelligence-failure",
)


@pytest.fixture(autouse=True)
def clean_runtime_data() -> Iterator[None]:
    for conversation_id in CONVERSATION_IDS:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)

    yield

    for conversation_id in CONVERSATION_IDS:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)


def make_decision_input(property_count: int = 2) -> DecisionInput:
    return DecisionInput(
        living_model=LivingModel(
            conversation_id="decision-intelligence-prompt",
            profile=LivingModelProfile(
                budget=6000,
                commute_minutes=30,
            ),
            decision_memory=[],
        ),
        properties=[
            PropertyDecisionInput(
                id=f"property-{index}",
                title=f"候选 {index}",
                rent=5600 + index * 300,
                commute_minutes=20 + index * 10,
            )
            for index in range(property_count)
        ],
    )


def prepare_runtime(conversation_id: str) -> Property:
    profile_manager.merge(
        conversation_id=conversation_id,
        patch=LivingProfilePatch(
            budget=6000,
            commute_minutes=30,
            preferred_city="深圳",
        ),
        latest_insights=[],
    )
    return property_manager.create(
        conversation_id=conversation_id,
        property_=Property(
            title="当前候选",
            district="南山",
            rent=5800,
            commute_minutes=25,
            pet_friendly=True,
        ),
    )


def ready_json(property_id: str) -> str:
    return json.dumps(
        {
            "status": "ready",
            "summary": "当前房源在预算与通勤之间形成较合理的平衡。",
            "best_property_id": property_id,
            "reasons": [
                {
                    "title": "通勤优势",
                    "description": "当前通勤时间符合已知要求。",
                },
            ],
            "trade_offs": [
                {
                    "title": "预算取舍",
                    "description": "获得较短通勤，同时使用大部分预算。",
                },
            ],
            "confidence": 0.8,
        },
        ensure_ascii=False,
    )


def test_reasoning_covers_advantages_risks_conflicts_and_trade_offs() -> None:
    guidance = decision_intelligence.build(property_count=2)

    assert "advantages" in guidance
    assert "risks" in guidance
    assert "conflicts" in guidance
    assert "trade-off" in guidance
    assert "supported benefit" in guidance
    assert "supported cost" in guidance


def test_reasoning_preserves_context_priority() -> None:
    prompt = build_decision_prompt(
        make_decision_input(),
        DecisionContext(
            conversation_id="decision-intelligence-prompt",
            recent_decisions=[],
        ),
    )

    assert "Current Facts > Living Model > Decision History" in prompt
    assert "History may provide continuity but cannot create facts" in prompt
    assert prompt.index("Current Property List:") < prompt.index(
        "LIVING MODEL:",
    )
    assert prompt.index("LIVING MODEL:") < prompt.index(
        "Recent Decision History:",
    )


def test_single_candidate_reasoning_does_not_claim_comparison() -> None:
    guidance = decision_intelligence.build(property_count=1)

    assert "There is one candidate" in guidance
    assert "without claiming a comparison" in guidance


def test_reasoning_failure_uses_safe_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_property_count: int) -> str:
        raise RuntimeError("guidance unavailable")

    monkeypatch.setattr(decision_intelligence, "_build", fail)

    assert decision_intelligence.build(2) == FALLBACK_DECISION_REASONING


def test_runtime_uses_reasoning_and_calls_model_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = "decision-intelligence-runtime"
    property_ = prepare_runtime(conversation_id)
    assert property_.id is not None
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return ready_json(property_.id)

    monkeypatch.setattr(ai_client, "generate_json", generate)

    result = decision_service.generate(conversation_id)

    assert result.status == "ready"
    assert len(result.trade_offs) == 1
    assert len(prompts) == 1
    assert "DECISION REASONING:" in prompts[0]
    assert "advantages" in prompts[0]
    assert conversation_id not in prompts[0]


def test_reasoning_failure_does_not_block_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = "decision-intelligence-failure"
    property_ = prepare_runtime(conversation_id)
    assert property_.id is not None
    call_count = 0

    def fail(_property_count: int) -> str:
        raise RuntimeError("guidance unavailable")

    def generate(prompt: str) -> str:
        nonlocal call_count
        call_count += 1
        assert FALLBACK_DECISION_REASONING in prompt
        return ready_json(property_.id)

    monkeypatch.setattr(decision_intelligence, "_build", fail)
    monkeypatch.setattr(ai_client, "generate_json", generate)

    result = decision_service.generate(conversation_id)

    assert result.status == "ready"
    assert call_count == 1
