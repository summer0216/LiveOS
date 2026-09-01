import json
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest

from app.core.ai_client import ai_client
from app.models.decision_memory import DecisionMemoryCategory
from app.models.profile import LivingProfile
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.runtime.memory_context import (
    DecisionMemoryContext,
    DecisionMemoryContextItem,
)
from app.schemas.decision_context import DecisionContext
from app.services.decision_context_builder import decision_context_builder
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.living_model_builder import (
    LivingModelBuilder,
    living_model_builder,
)
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from tests.ids import uuid_for

CONVERSATION_IDS = (
    "living-model-runtime",
    "living-model-failure",
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


def memory_item(content: str) -> DecisionMemoryContextItem:
    return DecisionMemoryContextItem(
        category=DecisionMemoryCategory.PRIORITY,
        content=content,
        confidence=0.9,
        evidence_count=2,
        updated_at=datetime.now(UTC),
    )


def memory_context(
    conversation_id: str,
    memories: list[DecisionMemoryContextItem] | None = None,
) -> DecisionMemoryContext:
    return DecisionMemoryContext(
        conversation_id=conversation_id,
        memories=memories or [],
    )


def complete_profile() -> LivingProfile:
    return LivingProfile(
        work_location="南山科技园",
        budget=6000,
        commute_minutes=30,
        preferred_city="深圳",
        family_size=2,
        has_pet=False,
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
        property_=Property(title="候选房源", rent=5800),
    )


def ready_json(property_id: str) -> str:
    return json.dumps(
        {
            "status": "ready",
            "summary": "当前候选房源符合统一 Living Model。",
            "best_property_id": property_id,
            "reasons": [
                {
                    "title": "Living Model",
                    "description": "预算与当前租金匹配。",
                },
            ],
            "trade_offs": [],
            "confidence": 0.8,
            "decision_gap": "当前候选的实际租金是否符合 Living Model。",
        },
        ensure_ascii=False,
    )


def test_build_combines_profile_and_memory_context() -> None:
    memory = memory_item("用户长期优先考虑较短通勤。")

    model = LivingModelBuilder().build(
        " conversation-a ",
        complete_profile(),
        memory_context("conversation-a", [memory]),
    )

    assert model.conversation_id == "conversation-a"
    assert model.profile.budget == 6000
    assert model.profile.has_pet is False
    assert model.decision_memory == [memory]


def test_empty_profile_builds_valid_living_model() -> None:
    model = LivingModelBuilder().build(
        "conversation-a",
        LivingProfile(),
        memory_context("conversation-a", [memory_item("稳定偏好")]),
    )

    assert all(value is None for value in model.profile.model_dump().values())
    assert len(model.decision_memory) == 1


def test_empty_memory_builds_valid_living_model() -> None:
    model = LivingModelBuilder().build(
        "conversation-a",
        complete_profile(),
        memory_context("conversation-a"),
    )

    assert model.profile.preferred_city == "深圳"
    assert model.decision_memory == []


def test_conversation_mismatch_degrades_to_empty_model() -> None:
    model = LivingModelBuilder().build(
        "conversation-a",
        complete_profile(),
        memory_context("conversation-b", [memory_item("隔离数据")]),
    )

    assert model.conversation_id == "conversation-a"
    assert model.decision_memory == []
    assert all(value is None for value in model.profile.model_dump().values())


def test_builder_does_not_mutate_inputs() -> None:
    profile = complete_profile()
    context = memory_context(
        "conversation-a",
        [memory_item("稳定偏好")],
    )
    profile_snapshot = LivingProfile(**vars(profile))
    context_snapshot = context.model_copy(deep=True)

    model = LivingModelBuilder().build(
        "conversation-a",
        profile,
        context,
    )

    assert profile == profile_snapshot
    assert context == context_snapshot
    assert model.decision_memory[0] is not context.memories[0]


def test_builder_failure_degrades_without_logging_private_content(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    private_content = "PRIVATE USER CONTENT"
    builder = LivingModelBuilder()

    def fail_build(*_args: object) -> None:
        raise RuntimeError("Builder unavailable")

    monkeypatch.setattr(builder, "_build", fail_build)
    model = builder.build(
        "conversation-a",
        LivingProfile(work_location=private_content),
        memory_context("conversation-a", [memory_item(private_content)]),
    )

    assert model.decision_memory == []
    assert model.profile.work_location is None
    assert private_content not in caplog.text


def test_decision_runtime_uses_living_model_and_one_model_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("living-model-runtime")
    property_ = prepare_runtime(conversation_id)
    assert property_.id is not None
    prompts: list[str] = []

    monkeypatch.setattr(
        decision_context_builder,
        "build",
        lambda _conversation_id: DecisionContext(
            conversation_id=conversation_id,
            memory_context=memory_context(
                conversation_id,
                [memory_item("用户长期优先考虑较短通勤。")],
            ),
        ),
    )

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return ready_json(property_.id or "")

    monkeypatch.setattr(ai_client, "generate_json", generate)

    result = decision_service.generate(conversation_id)

    assert result.status == "ready"
    assert len(prompts) == 1
    assert "LIVING MODEL:" in prompts[0]
    assert '"budget": 6000' in prompts[0]
    assert "用户长期优先考虑较短通勤。" in prompts[0]
    assert conversation_id not in prompts[0]
    assert "Current Living Profile:" not in prompts[0]
    assert "DECISION MEMORY:" not in prompts[0]


def test_runtime_continues_with_empty_model_after_builder_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("living-model-failure")
    property_ = prepare_runtime(conversation_id)
    assert property_.id is not None
    prompts: list[str] = []

    monkeypatch.setattr(
        living_model_builder,
        "_build",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("Unavailable")),
    )

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return ready_json(property_.id or "")

    monkeypatch.setattr(ai_client, "generate_json", generate)

    result = decision_service.generate(conversation_id)

    assert result.status == "ready"
    assert len(prompts) == 1
    assert '"decision_memory": []' in prompts[0]
    assert '"budget": null' in prompts[0]
