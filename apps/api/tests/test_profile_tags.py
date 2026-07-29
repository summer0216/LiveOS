from fastapi.testclient import TestClient

from app.main import app
from app.models.profile_patch import LivingProfilePatch
from app.services.profile_manager import profile_manager

conversation_id = "profile-tags-test"
profile_manager.merge(
    conversation_id=conversation_id,
    patch=LivingProfilePatch(),
    latest_insights=[],
)

client = TestClient(app)
response = client.patch(
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

invalid_response = client.patch(
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
profile_manager.delete(conversation_id)
