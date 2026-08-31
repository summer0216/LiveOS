import json
from uuid import UUID, uuid4

import pytest

from app.models.action_progress import (
    ActionProgressStatus,
    ActionProgressUpdate,
    VerificationOutcomeStatus,
)
from app.models.decision_memory import DecisionMemoryCategory
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.schemas.decision import DecisionReason, DecisionResult, DecisionTradeOff
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_action_progress import decision_action_progress_service
from app.services.decision_context_builder import decision_context_builder
from app.services.decision_memory_service import decision_memory_service
from app.services.decision_record_service import decision_record_service
from app.services.profile_intelligence import profile_intelligence
from tests.ids import uuid_for


def analysis_json() -> str:
    return json.dumps(
        {
            "work_location": None,
            "budget": None,
            "commute_minutes": None,
            "preferred_city": None,
            "family_size": None,
            "has_pet": None,
            "clear_fields": [],
            "decision_relevant_feedback": {
                "relevant": False,
                "observation": None,
                "judgment": None,
                "observed_commute_minutes": None,
            },
            "decision_challenge": {
                "relevant": False,
                "kind": None,
                "subject": None,
                "statement": None,
                "target_property_id": None,
            },
            "action_progress_update": {"relevant": False, "status": None},
            "verification_outcome_update": {
                "relevant": False,
                "status": None,
                "evidence": [],
            },
        },
        ensure_ascii=False,
    )


def save_ready(
    conversation_id: str,
    *,
    property_id: str | None = None,
    next_text: str = "核实房源城市。",
):
    conversation_manager.get_or_create(conversation_id)
    return decision_record_service.save(
        conversation_id,
        DecisionResult(
            status="ready",
            summary=f"当前方案可行。 下一步：{next_text}",
            best_property_id=property_id or str(uuid4()),
            reasons=[DecisionReason(title="判断", description="当前判断依据。")],
            trade_offs=[DecisionTradeOff(title="取舍", description="当前取舍依据。")],
            confidence=0.8,
        ),
    )


def apply_outcome(
    monkeypatch: pytest.MonkeyPatch,
    conversation_id: str,
    message: str,
) -> None:
    analysis = profile_intelligence._build_analysis(analysis_json(), message)
    monkeypatch.setattr(profile_intelligence, "analyze", lambda _history: analysis)
    chat_service._update_profile(conversation_id, [])


def test_outcome_creates_learning_with_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-learning-creation")
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)

    apply_outcome(monkeypatch, conversation_id, "确认过了，不在深圳，在成都。")

    state = decision_action_progress_service.current_state(conversation_id)
    memories = decision_memory_service.list_memories(conversation_id)

    assert state is not None
    assert len(memories) == 1
    learning = memories[0]
    assert learning.category == DecisionMemoryCategory.EVIDENCE_RELIABILITY
    assert learning.source_action_id == UUID(state.id)
    assert learning.source_action_key == state.action_key
    assert learning.source_outcome_status == VerificationOutcomeStatus.DISCONFIRMED
    assert learning.source_decision_record_id == UUID(state.decision_record_id)
    assert learning.evidence_record_ids == [learning.source_decision_record_id]


def test_corrected_outcome_replaces_learning_for_same_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-learning-correction")
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)

    apply_outcome(monkeypatch, conversation_id, "确认过了，不在深圳，在成都。")
    first = decision_memory_service.list_memories(conversation_id)[0]
    apply_outcome(monkeypatch, conversation_id, "确认了，就在深圳南山。")
    memories = decision_memory_service.list_memories(conversation_id)

    assert len(memories) == 1
    assert memories[0].id == first.id
    assert memories[0].source_outcome_status == VerificationOutcomeStatus.CONFIRMED


def test_new_action_does_not_overwrite_unrelated_learning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-learning-isolation")
    first = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(first)
    apply_outcome(monkeypatch, conversation_id, "问过了，中介也确认不了。")

    second = save_ready(conversation_id, next_text="比较另一套具体房源。")
    decision_action_progress_service.reconcile_ready_record(second)
    apply_outcome(monkeypatch, conversation_id, "确认了，就在深圳南山。")
    memories = decision_memory_service.list_memories(conversation_id)

    assert len(memories) == 2
    assert {memory.source_outcome_status for memory in memories} == {
        VerificationOutcomeStatus.INCONCLUSIVE,
        VerificationOutcomeStatus.CONFIRMED,
    }
    assert len({memory.source_action_id for memory in memories}) == 2


def test_learning_is_available_through_existing_decision_memory_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-learning-context")
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)
    apply_outcome(monkeypatch, conversation_id, "问过了，中介也确认不了。")

    context = decision_context_builder.build(conversation_id)

    assert len(context.memory_context.memories) == 1
    assert (
        context.memory_context.memories[0].category
        == DecisionMemoryCategory.EVIDENCE_RELIABILITY
    )


@pytest.mark.parametrize(
    ("case", "analysis"),
    (
        (
            "completed",
            ProfileAnalysis(
                patch=LivingProfilePatch(),
                action_progress_update=ActionProgressUpdate(
                    relevant=True,
                    status=ActionProgressStatus.COMPLETED,
                ),
            ),
        ),
        ("ordinary", ProfileAnalysis(patch=LivingProfilePatch())),
    ),
)
def test_completed_only_and_ordinary_turns_do_not_create_learning(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    analysis: ProfileAnalysis,
) -> None:
    conversation_id = uuid_for(f"decision-learning-none-{case}")
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)
    monkeypatch.setattr(profile_intelligence, "analyze", lambda _history: analysis)

    causes = chat_service._update_profile(conversation_id, [])

    assert causes == ()
    assert decision_memory_service.list_memories(conversation_id) == []


def test_outcome_learning_keeps_existing_single_decision_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-learning-exactly-once")
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)

    analysis = profile_intelligence._build_analysis(
        analysis_json(),
        "问过了，中介也确认不了。",
    )
    monkeypatch.setattr(profile_intelligence, "analyze", lambda _history: analysis)

    causes = chat_service._update_profile(conversation_id, [])

    assert len(causes) == 1
    assert causes[0].source == "VERIFICATION_OUTCOME"
    assert len(decision_memory_service.list_memories(conversation_id)) == 1
