from datetime import UTC, datetime

from app.models.action_progress import (
    ActionProgressStatus,
    LatestVerifiedAction,
    VerificationEvidence,
    VerificationOutcomeStatus,
)
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.schemas.decision import DecisionReason, DecisionResult
from app.services.candidate_decision_state import project_candidate_decision_states
from app.services.conversation_manager import conversation_manager
from app.services.decision_record_service import decision_record_service
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.stores.runtime import latest_verified_action_store
from tests.ids import uuid_for


def _properties(conversation_id: str) -> tuple[Property, Property]:
    first = property_manager.create(
        conversation_id,
        Property(title="候选 A", commute_minutes=25, rent=5500),
    )
    second = property_manager.create(
        conversation_id,
        Property(title="候选 B", commute_minutes=30, rent=5800),
    )
    return first, second


def _verified_action(
    conversation_id: str,
    property_id: str,
    *,
    outcome: VerificationOutcomeStatus,
    field: str = "commute_minutes",
    value: int | str = 80,
    statement: str = "工作日高峰实测通勤约80分钟，无法接受。",
) -> None:
    record = decision_record_service.save(
        conversation_id,
        DecisionResult(
            status="ready",
            summary="当前候选可以核实。下一步：实测一次工作日高峰通勤。",
            best_property_id=property_id,
            reasons=[DecisionReason(title="当前候选", description="需要现实核实。")],
            decision_gap="实际通勤是否符合要求。",
        ),
    )
    timestamp = datetime.now(UTC)
    latest_verified_action_store.save(
        LatestVerifiedAction(
            action_id=uuid_for(f"verified-{conversation_id}"),
            conversation_id=conversation_id,
            decision_record_id=record.id,
            action_key="verified-action",
            next_text="实测一次工作日高峰通勤。",
            status=ActionProgressStatus.COMPLETED,
            outcome_status=outcome,
            verification_evidence=(
                VerificationEvidence(
                    field=field,
                    value=value,
                    statement=statement,
                ),
            ),
            created_at=timestamp,
            updated_at=timestamp,
        )
    )


def test_verified_reality_rejects_only_its_source_candidate() -> None:
    conversation_id = uuid_for("candidate-state-rejected")
    conversation_manager.get_or_create(conversation_id)
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(commute_minutes=30, budget=6000),
        [],
    )
    candidate_a, candidate_b = _properties(conversation_id)
    assert candidate_a.id is not None
    assert candidate_b.id is not None
    _verified_action(
        conversation_id,
        candidate_a.id,
        outcome=VerificationOutcomeStatus.DISCONFIRMED,
    )

    states = project_candidate_decision_states(
        conversation_id,
        [candidate_a, candidate_b],
    )

    assert states[candidate_a.id].state == "REJECTED"
    assert states[candidate_a.id].reason == "工作日高峰实测通勤约80分钟，无法接受。"
    assert states[candidate_b.id].state == "ACTIVE"
    assert states[candidate_b.id].reason is None


def test_inconclusive_reality_weakens_its_source_candidate() -> None:
    conversation_id = uuid_for("candidate-state-weakened")
    conversation_manager.get_or_create(conversation_id)
    candidate_a, candidate_b = _properties(conversation_id)
    assert candidate_a.id is not None
    assert candidate_b.id is not None
    _verified_action(
        conversation_id,
        candidate_a.id,
        outcome=VerificationOutcomeStatus.INCONCLUSIVE,
        statement="中介暂时无法确认实际通勤情况。",
    )

    states = project_candidate_decision_states(
        conversation_id,
        [candidate_a, candidate_b],
    )

    assert states[candidate_a.id].state == "WEAKENED"
    assert states[candidate_b.id].state == "ACTIVE"


def test_missing_property_association_does_not_fabricate_state() -> None:
    conversation_id = uuid_for("candidate-state-no-association")
    conversation_manager.get_or_create(conversation_id)
    candidate_a, candidate_b = _properties(conversation_id)
    assert candidate_a.id is not None
    assert candidate_b.id is not None
    _verified_action(
        conversation_id,
        uuid_for("candidate-state-missing-property"),
        outcome=VerificationOutcomeStatus.DISCONFIRMED,
    )

    states = project_candidate_decision_states(
        conversation_id,
        [candidate_a, candidate_b],
    )

    assert states[candidate_a.id].state == "ACTIVE"
    assert states[candidate_b.id].state == "ACTIVE"


def test_candidate_without_contrary_reality_remains_active() -> None:
    conversation_id = uuid_for("candidate-state-active")
    conversation_manager.get_or_create(conversation_id)
    candidate_a, candidate_b = _properties(conversation_id)
    assert candidate_a.id is not None
    assert candidate_b.id is not None

    states = project_candidate_decision_states(
        conversation_id,
        [candidate_a, candidate_b],
    )

    assert states[candidate_a.id].state == "ACTIVE"
    assert states[candidate_b.id].state == "ACTIVE"
