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
from app.models.decision_unknown import DecisionUnknownStatus
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.schemas.decision import DecisionReason, DecisionResult, DecisionTradeOff
from app.services.chat_service import chat_service
from app.services.decision_action_progress import decision_action_progress_service
from app.services.decision_record_service import decision_record_service
from app.services.decision_unknown_service import decision_unknown_service
from app.services.property_manager import property_manager
from app.services.resume_resolver import resume_resolver
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation

client = TestClient(app)


def _ready_record(conversation_id: str, property_id: str):
    return decision_record_service.save(
        conversation_id,
        DecisionResult(
            status="ready",
            summary="当前判断可行。 下一步：晚上实地核实噪音。",
            best_property_id=property_id,
            reasons=[DecisionReason(title="判断", description="当前判断依据。")],
            trade_offs=[DecisionTradeOff(title="取舍", description="当前取舍依据。")],
            confidence=0.8,
        ),
    )


def test_choice_owned_unknown_has_stable_identity_and_open_projection() -> None:
    conversation_id = uuid_for("choice-owned-unknown")
    create_owned_conversation(client, conversation_id)
    property_ = property_manager.create(
        conversation_id,
        Property(title="候选 A", commute_minutes=24),
    )
    assert property_.id is not None

    first = decision_unknown_service.open_unknown(
        conversation_id,
        property_.id,
        "night_noise",
        "夜间噪音仍需确认",
    )
    repeated = decision_unknown_service.open_unknown(
        conversation_id,
        property_.id,
        "night_noise",
        "夜间噪音仍需确认",
    )

    assert repeated.id == first.id
    assert first.property_id == property_.id
    assert first.status == DecisionUnknownStatus.OPEN
    assert decision_unknown_service.list_open(conversation_id, property_.id) == [
        repeated
    ]

    response = client.get(
        "/api/properties",
        params={"conversation_id": conversation_id},
    )
    assert response.status_code == 200
    item = next(
        item for item in response.json()["items"] if item["id"] == property_.id
    )
    assert item["unknowns"] == [
        {
            "id": first.id,
            "property_id": property_.id,
            "topic": "night_noise",
            "status": "OPEN",
            "meaning": "夜间噪音仍需确认",
        }
    ]

    resolved = decision_unknown_service.resolve_unknown(conversation_id, first.id)
    assert resolved is not None
    assert resolved.status == DecisionUnknownStatus.RESOLVED
    assert decision_unknown_service.list_open(conversation_id, property_.id) == []


def test_action_can_bind_and_persist_choice_owned_unknown() -> None:
    conversation_id = uuid_for("action-unknown-binding")
    create_owned_conversation(client, conversation_id)
    property_ = property_manager.create(
        conversation_id,
        Property(title="候选 B", commute_minutes=31),
    )
    assert property_.id is not None
    unknown = decision_unknown_service.open_unknown(
        conversation_id,
        property_.id,
        "night_noise",
        "夜间噪音仍需确认",
    )
    record = _ready_record(conversation_id, property_.id)

    current = decision_action_progress_service.reconcile_ready_record(
        record,
        unknown_id=unknown.id,
    )
    persisted = decision_action_progress_service.current_state(conversation_id)

    assert current is not None
    assert current.unknown_id == unknown.id
    assert persisted is not None
    assert persisted.unknown_id == unknown.id


def test_action_rejects_unknown_from_other_choice_or_conversation() -> None:
    conversation_id = uuid_for("action-unknown-owner")
    other_conversation_id = uuid_for("action-unknown-other-conversation")
    create_owned_conversation(client, conversation_id)
    create_owned_conversation(client, other_conversation_id)
    property_a = property_manager.create(
        conversation_id,
        Property(title="候选 A", commute_minutes=24),
    )
    property_b = property_manager.create(
        conversation_id,
        Property(title="候选 B", commute_minutes=31),
    )
    other_property = property_manager.create(
        other_conversation_id,
        Property(title="其他候选", commute_minutes=42),
    )
    assert property_a.id and property_b.id and other_property.id
    same_conversation_unknown = decision_unknown_service.open_unknown(
        conversation_id,
        property_b.id,
        "night_noise",
        "夜间噪音仍需确认",
    )
    other_conversation_unknown = decision_unknown_service.open_unknown(
        other_conversation_id,
        other_property.id,
        "night_noise",
        "夜间噪音仍需确认",
    )
    record = _ready_record(conversation_id, property_a.id)

    with pytest.raises(ValueError, match="Action property"):
        decision_action_progress_service.reconcile_ready_record(
            record,
            unknown_id=same_conversation_unknown.id,
        )
    with pytest.raises(ValueError, match="same conversation"):
        decision_action_progress_service.reconcile_ready_record(
            record,
            unknown_id=other_conversation_unknown.id,
        )


def test_reality_completion_resolves_only_linked_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("reality-resolves-linked-unknown")
    create_owned_conversation(client, conversation_id)
    property_ = property_manager.create(
        conversation_id,
        Property(title="候选 C", commute_minutes=31),
    )
    assert property_.id is not None
    linked = decision_unknown_service.open_unknown(
        conversation_id,
        property_.id,
        "night_noise",
        "夜间噪音仍需确认",
    )
    unrelated = decision_unknown_service.open_unknown(
        conversation_id,
        property_.id,
        "parking",
        "停车仍需确认",
    )
    record = _ready_record(conversation_id, property_.id)
    decision_action_progress_service.reconcile_ready_record(
        record,
        unknown_id=linked.id,
    )

    analysis = ProfileAnalysis(
        patch=LivingProfilePatch(),
        action_progress_update=ActionProgressUpdate(
            relevant=True,
            status=ActionProgressStatus.COMPLETED,
        ),
        verification_outcome_update=VerificationOutcomeUpdate(
            relevant=True,
            status=VerificationOutcomeStatus.DISCONFIRMED,
            evidence=(
                VerificationEvidence(
                    field="statement",
                    value="夜间噪音较大",
                    statement="夜间噪音较大。",
                ),
            ),
        ),
    )

    from app.services.profile_intelligence import profile_intelligence

    monkeypatch.setattr(profile_intelligence, "analyze", lambda _history: analysis)
    chat_service._update_profile(conversation_id, [])

    remaining = decision_unknown_service.list_open(conversation_id, property_.id)
    assert [item.id for item in remaining] == [unrelated.id]
    updated_record = decision_record_service.get_by_id(conversation_id, record.id)
    assert updated_record is not None
    assert updated_record.recommendation_invalidated is True
    resumed = resume_resolver.resolve_conversation(
        client.cookies.get(COOKIE_NAME),
        conversation_id,
    )
    assert resumed is not None
    assert resumed.decision is None
