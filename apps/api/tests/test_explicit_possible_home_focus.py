"""The current user-named, grounded Home is the only auto-focus source."""

from fastapi.testclient import TestClient

from app.api.chat import _stream_events
from app.main import app
from app.models.decision_geography import DecisionGeography
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, Property
from app.services.chat_service import (
    WorldConsequenceReady,
    _explicit_possible_home_focus,
    _ground_explicit_possible_home,
)
from app.services.geographic_resolution import GeographicResolutionResult
from app.services.property_manager import property_manager
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_only_unique_grounded_user_home_becomes_focus(monkeypatch):
    client = TestClient(app)
    conversation_id = uuid_for("explicit-possible-home-focus")
    create_owned_conversation(client, conversation_id)
    home = property_manager.create(conversation_id, Property(title="龙湖时代天街"))
    assert home.id
    analysis = ProfileAnalysis(
        patch=LivingProfilePatch(), choices=[Property(title="龙湖时代天街")],
    )
    geography = DecisionGeography(
        intent_established=True, intent_type="residence", identity="龙湖时代天街",
        identity_source="USER", geographic_scope="LOCAL", status="GROUNDED",
        lng=103.917856, lat=30.754633,
    )
    assert _explicit_possible_home_focus(conversation_id, analysis, geography) is None
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
    assert _explicit_possible_home_focus(conversation_id, analysis, geography) == home.id
    persisted = client.get(f"/api/properties?conversation_id={conversation_id}")
    assert persisted.status_code == 200
    assert any(item["id"] == home.id and item["geographic_status"] == "GROUNDED"
               for item in persisted.json()["items"])
    events = list(_stream_events(iter([WorldConsequenceReady(home.id)]), conversation_id))
    event = next(item for item in events if "event: world-consequence-ready" in item)
    assert f'"focus_property_id": "{home.id}"' in event

    assert _explicit_possible_home_focus(
        conversation_id, analysis, DecisionGeography(
            **{**geography.__dict__, "status": "UNRESOLVED"},
        ),
    ) is None
    ambiguous = ProfileAnalysis(
        patch=LivingProfilePatch(),
        choices=[Property(title="龙湖时代天街"), Property(title="另一处")],
    )
    assert _explicit_possible_home_focus(conversation_id, ambiguous, geography) is None
    assert _explicit_possible_home_focus(
        conversation_id, analysis, DecisionGeography(
            **{**geography.__dict__, "lng": 106.6},
        ),
    ) is None
