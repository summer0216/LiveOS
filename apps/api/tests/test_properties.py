from fastapi.testclient import TestClient

from app.main import app
from app.services.property_manager import property_manager
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation

client = TestClient(app)


def test_property_crud_and_conversation_isolation() -> None:
    conversation_a = uuid_for("property-list-a")
    conversation_b = uuid_for("property-list-b")
    property_manager.delete_conversation(conversation_a)
    property_manager.delete_conversation(conversation_b)

    create_owned_conversation(client, conversation_a)
    create_owned_conversation(client, conversation_b)

    empty_response = client.get(
        "/api/properties",
        params={"conversation_id": conversation_a},
    )
    assert empty_response.status_code == 200
    assert empty_response.json() == {"items": []}

    first_response = client.post(
        "/api/properties",
        json={
            "conversation_id": conversation_a,
            "title": "南山一号",
            "district": "南山",
            "rent": 5800,
            "area": 65,
            "bedrooms": 2,
            "bathrooms": 1,
            "commute_minutes": 25,
            "pet_friendly": True,
        },
    )
    assert first_response.status_code == 201
    first_property = first_response.json()
    assert first_property["id"]
    assert first_property["conversation_id"] == conversation_a

    second_response = client.post(
        "/api/properties",
        json={
            "conversation_id": conversation_a,
            "title": "南山二号",
        },
    )
    assert second_response.status_code == 201

    isolated_response = client.post(
        "/api/properties",
        json={
            "conversation_id": conversation_b,
            "title": "福田一号",
        },
    )
    assert isolated_response.status_code == 201

    list_a_response = client.get(
        "/api/properties",
        params={"conversation_id": conversation_a},
    )
    assert list_a_response.status_code == 200
    assert len(list_a_response.json()["items"]) == 2

    list_b_response = client.get(
        "/api/properties",
        params={"conversation_id": conversation_b},
    )
    assert list_b_response.status_code == 200
    assert len(list_b_response.json()["items"]) == 1

    delete_response = client.delete(
        f"/api/properties/{first_property['id']}",
    )
    assert delete_response.status_code == 204

    remaining_response = client.get(
        "/api/properties",
        params={"conversation_id": conversation_a},
    )
    assert len(remaining_response.json()["items"]) == 1

    missing_delete_response = client.delete(
        "/api/properties/missing-property",
    )
    assert missing_delete_response.status_code == 404

    property_manager.delete_conversation(conversation_a)
    property_manager.delete_conversation(conversation_b)
