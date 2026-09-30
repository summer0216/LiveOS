"""A grounded user-named Home enters SEE without an automatic Focus command."""

import json

from fastapi.testclient import TestClient

from app.api.chat import _stream_events
from app.main import app
from app.models.decision_geography import DecisionGeography
from app.models.property import GeographicPrecision, Property
from app.models.work_subject import WorkSubject
from app.services.chat_service import (
    WorldConsequenceReady,
    _ground_explicit_possible_home,
)
from app.services.geographic_resolution import GeographicResolutionResult
from app.services.property_manager import property_manager
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_unique_grounded_user_home_remains_see_until_explicit_focus(monkeypatch):
    client = TestClient(app)
    conversation_id = uuid_for("explicit-possible-home-focus")
    create_owned_conversation(client, conversation_id)
    home = property_manager.create(conversation_id, Property(title="龙湖时代天街"))
    assert home.id
    geography = DecisionGeography(
        intent_established=True, intent_type="residence", identity="龙湖时代天街",
        identity_source="USER", geographic_scope="LOCAL", status="GROUNDED",
        lng=103.917856, lat=30.754633,
    )
    monkeypatch.setattr(
        "app.services.chat_service.geographic_resolver.resolve_local_area",
        lambda *_args: GeographicResolutionResult(
            status="GROUNDED", geographic_identity="成都市龙湖时代天街10号楼2单元",
            geographic_precision=GeographicPrecision.AREA,
            geographic_scope="LOCAL", lng=103.917856, lat=30.754633,
        ),
    )
    _ground_explicit_possible_home(
        conversation_id, home.id, title="龙湖时代天街",
        geography=geography, city_context="成都市",
    )
    persisted = client.get(f"/api/properties?conversation_id={conversation_id}")
    assert persisted.status_code == 200
    assert any(item["id"] == home.id and item["geographic_status"] == "GROUNDED"
               for item in persisted.json()["items"])
    events = list(_stream_events(iter([WorldConsequenceReady()]), conversation_id))
    event = next(item for item in events if "event: world-consequence-ready" in item)
    assert "data: true" in event
    assert "focus_property_id" not in event


def test_world_consequence_transport_preserves_subject_and_property_focus():
    subject = WorkSubject(
        identity="融科资讯中心",
        geographic_identity="北京市海淀区融科资讯中心",
        geographic_precision="PLACE",
        geographic_status="GROUNDED",
        lng=116.326178,
        lat=39.984098,
    )
    subject_event = next(
        item for item in _stream_events(iter([
            WorldConsequenceReady(focus_subject=subject),
        ]))
        if "event: world-consequence-ready" in item
    )
    subject_payload = json.loads(subject_event.split("data: ", 1)[1])
    assert subject_payload == {"focus_subject": {
        "identity": "融科资讯中心",
        "geographic_identity": "北京市海淀区融科资讯中心",
        "geographic_precision": "PLACE",
        "geographic_status": "GROUNDED",
        "lng": 116.326178,
        "lat": 39.984098,
        "relationship": "WORK",
    }}

    property_event = next(
        item for item in _stream_events(iter([
            WorldConsequenceReady(focus_property_id="property-1"),
        ]))
        if "event: world-consequence-ready" in item
    )
    assert json.loads(property_event.split("data: ", 1)[1]) == {
        "focus_property_id": "property-1",
    }
