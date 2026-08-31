from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.ownership import COOKIE_NAME
from app.main import app
from app.models.action_progress import (
    ActionProgressStatus,
    ActionProgressUpdate,
    VerificationEvidence,
    VerificationOutcomeStatus,
    VerificationOutcomeUpdate,
)
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.schemas.decision import DecisionReason, DecisionResult, DecisionTradeOff
from app.schemas.decision_record import DecisionRecord
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_action_progress import decision_action_progress_service
from app.services.decision_memory_service import decision_memory_service
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.profile_intelligence import profile_intelligence
from app.stores.runtime import decision_action_state_store, latest_verified_action_store


def save_ready(
    conversation_id: str,
    *,
    owner_id: str | None = None,
    property_id: str | None = None,
    next_text: str = "核实房源城市。",
) -> DecisionRecord:
    if owner_id is None:
        conversation_manager.get_or_create(conversation_id)
    else:
        conversation_manager.get_or_create(conversation_id, owner_id)
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
    conversation_id: str,
    status: VerificationOutcomeStatus = VerificationOutcomeStatus.CONFIRMED,
    statement: str = "已确认房源位于深圳。",
):
    return decision_action_progress_service.apply_update(
        conversation_id,
        ActionProgressUpdate(
            relevant=True,
            status=ActionProgressStatus.COMPLETED,
        ),
        VerificationOutcomeUpdate(
            relevant=True,
            status=status,
            evidence=(
                VerificationEvidence(
                    field="statement",
                    value=statement,
                    statement=statement,
                ),
            ),
        ),
    )


def test_verified_action_survives_new_logical_action() -> None:
    conversation_id = str(uuid4())
    property_id = str(uuid4())
    first = save_ready(conversation_id, property_id=property_id)
    decision_action_progress_service.reconcile_ready_record(first)
    completed = apply_outcome(conversation_id)
    verified = decision_action_progress_service.latest_verified_state(conversation_id)

    changed = save_ready(
        conversation_id,
        property_id=property_id,
        next_text="比较两套具体房源。",
    )
    current = decision_action_progress_service.reconcile_ready_record(changed)

    assert completed is not None
    assert verified is not None
    assert current is not None
    assert current.action_id != completed.action_id
    assert current.status is None
    assert current.outcome_status is None
    assert current.verification_evidence == ()
    assert verified.action_id == completed.action_id
    assert verified.status == ActionProgressStatus.COMPLETED
    assert verified.outcome_status == VerificationOutcomeStatus.CONFIRMED
    assert verified.verification_evidence[0].provenance == "USER_REPORTED"


def test_progress_only_and_equivalent_ready_do_not_replace_verified_action() -> None:
    conversation_id = str(uuid4())
    property_id = str(uuid4())
    first = save_ready(conversation_id, property_id=property_id)
    decision_action_progress_service.reconcile_ready_record(first)
    apply_outcome(conversation_id)
    verified = decision_action_progress_service.latest_verified_state(conversation_id)

    progress = decision_action_progress_service.apply_update(
        conversation_id,
        ActionProgressUpdate(
            relevant=True,
            status=ActionProgressStatus.PLANNED,
        ),
    )
    equivalent = save_ready(conversation_id, property_id=property_id)
    decision_action_progress_service.reconcile_ready_record(equivalent)
    after = decision_action_progress_service.latest_verified_state(conversation_id)

    assert verified is not None
    assert progress is not None
    assert after == verified


def test_new_verification_replaces_latest_verified_action() -> None:
    conversation_id = str(uuid4())
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)
    apply_outcome(
        conversation_id,
        VerificationOutcomeStatus.INCONCLUSIVE,
        "中介也确认不了。",
    )
    first = decision_action_progress_service.latest_verified_state(conversation_id)
    apply_outcome(
        conversation_id,
        VerificationOutcomeStatus.CONFIRMED,
        "已确认房源位于深圳。",
    )
    latest = decision_action_progress_service.latest_verified_state(conversation_id)

    assert first is not None
    assert latest is not None
    assert latest.action_id == first.action_id
    assert latest.outcome_status == VerificationOutcomeStatus.CONFIRMED
    assert latest.verification_evidence[0].statement == "已确认房源位于深圳。"


def test_learning_uses_latest_verified_action_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = str(uuid4())
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)
    analysis = ProfileAnalysis(
        patch=LivingProfilePatch(),
        action_progress_update=ActionProgressUpdate(
            relevant=True,
            status=ActionProgressStatus.COMPLETED,
        ),
        verification_outcome_update=VerificationOutcomeUpdate(
            relevant=True,
            status=VerificationOutcomeStatus.CONFIRMED,
            evidence=(
                VerificationEvidence(
                    field="statement",
                    value="已确认房源位于深圳。",
                    statement="已确认房源位于深圳。",
                ),
            ),
        ),
    )
    monkeypatch.setattr(profile_intelligence, "analyze", lambda _history: analysis)

    chat_service._update_profile(conversation_id, [])
    verified = decision_action_progress_service.latest_verified_state(conversation_id)
    learning = decision_memory_service.list_memories(conversation_id)[0]

    assert verified is not None
    assert learning.source_action_id == UUID(verified.action_id)
    assert learning.source_action_key == verified.action_key
    assert learning.source_outcome_status == verified.outcome_status
    assert learning.source_decision_record_id == UUID(verified.decision_record_id)


def test_resume_restores_current_and_latest_verified_actions_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_id = str(uuid4())
    conversation_id = str(uuid4())
    property_id = str(uuid4())
    first = save_ready(
        conversation_id,
        owner_id=owner_id,
        property_id=property_id,
    )
    decision_action_progress_service.reconcile_ready_record(first)
    completed = apply_outcome(conversation_id)
    second = save_ready(
        conversation_id,
        property_id=property_id,
        next_text="比较两套具体房源。",
    )
    decision_action_progress_service.reconcile_ready_record(second)
    before_current = decision_action_state_store.get(conversation_id)
    before_verified = latest_verified_action_store.get(conversation_id)

    monkeypatch.setattr(
        profile_intelligence,
        "analyze",
        lambda _history: pytest.fail("Resume must not call Profile Intelligence."),
    )
    monkeypatch.setattr(
        decision_service,
        "generate",
        lambda _conversation_id: pytest.fail("Resume must not generate Decision."),
    )
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, owner_id)
    response = client.get("/api/resume", params={"conversation_id": conversation_id})

    assert completed is not None
    assert response.status_code == 200
    payload = response.json()
    assert payload["action_progress"]["status"] is None
    assert payload["latest_verified_action"]["action_id"] == completed.action_id
    assert payload["latest_verified_action"]["status"] == "COMPLETED"
    assert payload["latest_verified_action"]["outcome_status"] == "CONFIRMED"
    assert decision_action_state_store.get(conversation_id) == before_current
    assert latest_verified_action_store.get(conversation_id) == before_verified
