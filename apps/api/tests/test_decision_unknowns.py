from fastapi.testclient import TestClient

from app.main import app
from app.models.decision_unknown import DecisionUnknownStatus
from app.models.property import Property
from app.services.decision_unknown_service import decision_unknown_service
from app.services.property_manager import property_manager
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation

client = TestClient(app)


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
