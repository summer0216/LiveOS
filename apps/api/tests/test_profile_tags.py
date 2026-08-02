from fastapi.testclient import TestClient

from app.main import app
from app.models.profile_patch import LivingProfilePatch
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from tests.ownership import create_owned_conversation


def test_preference_tags_require_the_conversation_owner() -> None:
    conversation_id = "profile-tags-test"
    owner_client = TestClient(app)
    other_client = TestClient(app)

    create_owned_conversation(owner_client, conversation_id)

    profile_manager.merge(
        conversation_id=conversation_id,
        patch=LivingProfilePatch(),
        latest_insights=[],
    )

    response = owner_client.patch(
        f"/api/profiles/{conversation_id}/tags",
        json={
            "preference_tags": {
                "preference": ["两居室", "步行便利"],
                "commute": ["靠近 Caltrain"],
                "lifestyle": ["周末安静"],
                "budget": ["预算 $4,500/月"],
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["preference_tags"]["preference"] == [
        "两居室",
        "步行便利",
    ]

    forbidden = other_client.patch(
        f"/api/profiles/{conversation_id}/tags",
        json={
            "preference_tags": {
                "preference": ["其它用户"],
                "commute": [],
                "lifestyle": [],
                "budget": [],
            },
        },
    )
    assert forbidden.status_code == 404

    invalid_response = owner_client.patch(
        f"/api/profiles/{conversation_id}/tags",
        json={
            "preference_tags": {
                "preference": ["两居室", "两居室"],
                "commute": [],
                "lifestyle": [],
                "budget": [],
            },
        },
    )
    assert invalid_response.status_code == 422

    property_manager.delete_conversation(conversation_id)
    profile_manager.delete(conversation_id)
