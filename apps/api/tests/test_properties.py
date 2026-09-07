from fastapi.testclient import TestClient

from app.main import app
from app.services.property_manager import property_manager
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation

client = TestClient(app)


def test_property_crud_and_owner_workspace_sharing() -> None:
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
    assert len(list_a_response.json()["items"]) == 3

    list_b_response = client.get(
        "/api/properties",
        params={"conversation_id": conversation_b},
    )
    assert list_b_response.status_code == 200
    assert len(list_b_response.json()["items"]) == 3

    delete_response = client.delete(
        f"/api/properties/{first_property['id']}",
    )
    assert delete_response.status_code == 204

    remaining_response = client.get(
        "/api/properties",
        params={"conversation_id": conversation_a},
    )
    assert len(remaining_response.json()["items"]) == 2

    missing_delete_response = client.delete(
        "/api/properties/missing-property",
    )
    assert missing_delete_response.status_code == 404

    property_manager.delete_conversation(conversation_a)
    property_manager.delete_conversation(conversation_b)


def test_property_geographic_grounding_lifecycle_and_projection() -> None:
    conversation_id = uuid_for("property-geographic-grounding")
    create_owned_conversation(client, conversation_id)

    created = client.post(
        "/api/properties",
        json={"conversation_id": conversation_id, "title": "后海公寓"},
    )
    assert created.status_code == 201
    property_id = created.json()["id"]
    assert created.json()["geographic_status"] == "UNRESOLVED"
    assert created.json()["lng"] is None
    assert created.json()["lat"] is None

    unresolved = client.patch(
        f"/api/properties/{property_id}/geography",
        json={
            "conversation_id": conversation_id,
            "geographic_identity": "后海公寓",
            "geographic_status": "UNRESOLVED",
        },
    )
    assert unresolved.status_code == 200
    assert unresolved.json()["geographic_status"] == "UNRESOLVED"
    assert unresolved.json()["geographic_precision"] is None

    grounded = client.patch(
        f"/api/properties/{property_id}/geography",
        json={
            "conversation_id": conversation_id,
            "geographic_identity": "深圳市南山区后海公寓",
            "geographic_precision": "PLACE",
            "geographic_status": "GROUNDED",
            "lng": 113.929757,
            "lat": 22.510291,
        },
    )
    assert grounded.status_code == 200
    assert grounded.json()["geographic_status"] == "GROUNDED"
    assert grounded.json()["geographic_precision"] == "PLACE"
    assert grounded.json()["lng"] == 113.929757
    assert grounded.json()["lat"] == 22.510291

    projected = client.get(
        "/api/properties",
        params={"conversation_id": conversation_id},
    )
    assert projected.status_code == 200
    item = projected.json()["items"][0]
    assert item["geographic_status"] == "GROUNDED"
    assert item["geographic_identity"] == "深圳市南山区后海公寓"


def test_invalid_property_geographic_grounding_is_rejected() -> None:
    conversation_id = uuid_for("property-geographic-invalid")
    create_owned_conversation(client, conversation_id)
    created = client.post(
        "/api/properties",
        json={"conversation_id": conversation_id, "title": "未定位候选"},
    )
    property_id = created.json()["id"]

    missing_coordinates = client.patch(
        f"/api/properties/{property_id}/geography",
        json={
            "conversation_id": conversation_id,
            "geographic_identity": "未定位候选",
            "geographic_precision": "AREA",
            "geographic_status": "GROUNDED",
        },
    )
    assert missing_coordinates.status_code == 422

    unresolved_with_coordinates = client.patch(
        f"/api/properties/{property_id}/geography",
        json={
            "conversation_id": conversation_id,
            "geographic_status": "UNRESOLVED",
            "lng": 113.9,
            "lat": 22.5,
        },
    )
    assert unresolved_with_coordinates.status_code == 422
