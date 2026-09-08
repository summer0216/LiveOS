import json
from types import SimpleNamespace

from app.core.config import settings
from app.models.decision_geography import DecisionGeography
from app.models.property import GeographicStatus
from app.services import decision_geography_service as decision_geography_module
from app.services.profile_intelligence import profile_intelligence
from app.stores.database import Database
from app.stores.persistent import ConversationStore, DecisionGeographyStore
from tests.ids import uuid_for


def test_profile_intelligence_extracts_decision_geography_without_work_fact() -> None:
    analysis = profile_intelligence._build_analysis(
        json.dumps(
            {
                "decision_intent": {
                    "established": True,
                    "type": "RELOCATE_FOR_WORK",
                },
                "decision_geography": {
                    "identity": "深圳",
                    "status": "UNRESOLVED",
                    "lng": None,
                    "lat": None,
                },
            }
        ),
        "我准备去深圳找工作。",
    )

    assert analysis.decision_geography.intent_established is True
    assert analysis.decision_geography.intent_type == "RELOCATE_FOR_WORK"
    assert analysis.decision_geography.identity == "深圳"
    assert analysis.patch.work_location is None


def test_location_mention_without_decision_does_not_establish_geography() -> None:
    analysis = profile_intelligence._build_analysis(
        json.dumps({"decision_intent": {"established": False}}),
        "深圳今天下雨吗？",
    )

    assert analysis.decision_geography.intent_established is False
    assert analysis.decision_geography.identity is None


def test_decision_geography_resolves_and_persists_coordinates(monkeypatch) -> None:
    saved: list[DecisionGeography] = []
    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve",
        lambda *_args: SimpleNamespace(
            status="GROUNDED",
            lng=114.0579,
            lat=22.5431,
        ),
    )
    monkeypatch.setattr(
        decision_geography_module.decision_geography_store,
        "save",
        lambda _conversation_id, state: saved.append(state) or state,
    )

    state = decision_geography_module.decision_geography_service.apply(
        "conversation-id",
        intent_established=True,
        intent_type="RELOCATE_FOR_WORK",
        identity="深圳",
        api_key="server-key",
    )

    assert state is not None
    assert state.status == GeographicStatus.GROUNDED.value
    assert state.lng == 114.0579
    assert state.lat == 22.5431
    assert saved == [state]


def test_decision_geography_survives_database_reconnect() -> None:
    database = Database(settings.DATABASE_URL)
    database.initialize()
    conversation_id = uuid_for("decision-geography-persisted")
    owner_id = uuid_for("decision-geography-owner")
    conversations = ConversationStore(database)
    store = DecisionGeographyStore(database)

    conversations.delete(conversation_id)
    conversations.get_or_create(conversation_id, owner_id)
    state = store.save(
        conversation_id,
        DecisionGeography(
            intent_established=True,
            intent_type="RELOCATE_FOR_WORK",
            identity="深圳",
            status="GROUNDED",
            lng=114.0579,
            lat=22.5431,
        ),
    )

    reconnected_store = DecisionGeographyStore(Database(settings.DATABASE_URL))
    assert reconnected_store.get(conversation_id) == state
