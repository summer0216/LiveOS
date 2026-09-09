import json
from types import SimpleNamespace

from app.core.config import settings
from app.models.decision_geography import DecisionGeography
from app.models.property import GeographicPrecision, GeographicStatus
from app.services import decision_geography_service as decision_geography_module
from app.services.geographic_resolution import (
    GeographicResolutionResult,
    normalize_local_geographic_identity,
)
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
                    "source": "USER",
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


def test_assistant_inference_cannot_establish_decision_geography() -> None:
    analysis = profile_intelligence._build_analysis(
        json.dumps(
            {
                "decision_intent": {
                    "established": True,
                    "type": "RELOCATE",
                },
                "decision_geography": {
                    "identity": "深圳",
                    "source": "INFERRED",
                    "status": "UNRESOLVED",
                    "lng": None,
                    "lat": None,
                },
            }
        ),
        "我想去春熙路附近住",
    )

    assert analysis.decision_geography.intent_established is False
    assert analysis.decision_geography.identity == "深圳"
    assert analysis.decision_geography.identity_source == "INFERRED"


def test_latest_user_geography_replaces_assistant_inference() -> None:
    analysis = profile_intelligence._build_analysis(
        json.dumps(
            {
                "decision_intent": {
                    "established": True,
                    "type": "RELOCATE",
                },
                "decision_geography": {
                    "identity": "春熙路附近",
                    "source": "USER",
                    "status": "UNRESOLVED",
                    "lng": None,
                    "lat": None,
                },
            }
        ),
        "我想去春熙路附近住",
    )

    assert analysis.decision_geography.intent_established is True
    assert analysis.decision_geography.identity == "春熙路"
    assert analysis.decision_geography.identity_source == "USER"


def test_local_relation_modifiers_are_not_geographic_identity() -> None:
    assert normalize_local_geographic_identity("春熙路附近") == "春熙路"
    assert normalize_local_geographic_identity("春熙路周边") == "春熙路"
    assert normalize_local_geographic_identity("春熙路那边") == "春熙路"
    assert normalize_local_geographic_identity("春熙路一带") == "春熙路"


def test_identity_not_present_in_latest_user_turn_is_not_user_truth() -> None:
    analysis = profile_intelligence._build_analysis(
        json.dumps(
            {
                "decision_intent": {
                    "established": True,
                    "type": "RELOCATE",
                },
                "decision_geography": {
                    "identity": "深圳",
                    "source": "USER",
                    "status": "UNRESOLVED",
                    "lng": None,
                    "lat": None,
                },
            }
        ),
        "我想去春熙路附近住",
    )

    assert analysis.decision_geography.intent_established is False
    assert analysis.decision_geography.identity == "深圳"
    assert analysis.decision_geography.identity_source == "INFERRED"


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
        identity_source="USER",
        api_key="server-key",
    )

    assert state is not None
    assert state.status == GeographicStatus.GROUNDED.value
    assert state.lng == 114.0579
    assert state.lat == 22.5431
    assert saved == [state]


def test_local_decision_geography_uses_current_city_context(monkeypatch) -> None:
    calls: list[tuple[str, str | None]] = []
    saved: list[DecisionGeography] = []

    def resolve(title: str, context: str | None, _api_key: str):
        calls.append((title, context))
        if context is None:
            return GeographicResolutionResult(
                status="UNRESOLVED"
            )
        return GeographicResolutionResult(
            status="GROUNDED",
            geographic_identity="四川省成都市高新南区",
            lng=104.0657,
            lat=30.5436,
        )

    monkeypatch.setattr(decision_geography_module.geographic_resolver, "resolve", resolve)
    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve_city_context",
        lambda *_args: "成都市",
    )
    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve_local_area",
        lambda *_args: GeographicResolutionResult(status="UNRESOLVED"),
    )
    monkeypatch.setattr(
        decision_geography_module.decision_geography_store,
        "save",
        lambda _conversation_id, state: saved.append(state) or state,
    )

    state = decision_geography_module.decision_geography_service.apply(
        "conversation-id",
        intent_established=True,
        intent_type="RELOCATE",
        identity="高新南",
        identity_source="USER",
        api_key="server-key",
        current_geographic_reality=(104.0668, 30.5728),
    )

    assert calls == [("高新南", None), ("高新南", "成都市")]
    assert state == saved[0]
    assert state.status == GeographicStatus.GROUNDED.value
    assert (state.lng, state.lat) == (104.0657, 30.5436)


def test_explicit_city_does_not_use_current_city_context(monkeypatch) -> None:
    calls: list[tuple[str, str | None]] = []

    def resolve(title: str, context: str | None, _api_key: str):
        calls.append((title, context))
        return GeographicResolutionResult(
            status="GROUNDED",
            geographic_identity="广东省深圳市南山区",
            lng=114.0579,
            lat=22.5431,
        )

    monkeypatch.setattr(decision_geography_module.geographic_resolver, "resolve", resolve)
    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve_city_context",
        lambda *_args: (_ for _ in ()).throw(AssertionError("should not resolve context")),
    )
    monkeypatch.setattr(
        decision_geography_module.decision_geography_store,
        "save",
        lambda _conversation_id, state: state,
    )

    state = decision_geography_module.decision_geography_service.apply(
        "conversation-id",
        intent_established=True,
        intent_type="RELOCATE_FOR_WORK",
        identity="深圳南山",
        identity_source="USER",
        api_key="server-key",
        current_geographic_reality=(104.0668, 30.5728),
    )

    assert calls == [("深圳南山", None)]
    assert state is not None
    assert state.status == GeographicStatus.GROUNDED.value


def test_new_user_geography_overwrites_previous_inferred_city(monkeypatch) -> None:
    previous = DecisionGeography(
        intent_established=True,
        intent_type="RELOCATE_FOR_WORK",
        identity="深圳",
        status="GROUNDED",
        lng=114.0579,
        lat=22.5431,
    )
    saved: list[DecisionGeography] = []
    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve",
        lambda *_args: GeographicResolutionResult(
            status="GROUNDED",
            geographic_identity="四川省成都市春熙路",
            geographic_precision=GeographicPrecision.STREET,
            lng=104.078293,
            lat=30.65744,
        ),
    )
    monkeypatch.setattr(
        decision_geography_module.decision_geography_store,
        "get",
        lambda _conversation_id: previous,
    )
    monkeypatch.setattr(
        decision_geography_module.decision_geography_store,
        "save",
        lambda _conversation_id, state: saved.append(state) or state,
    )

    state = decision_geography_module.decision_geography_service.apply(
        "conversation-id",
        intent_established=True,
        intent_type="RELOCATE",
        identity="春熙路附近",
        identity_source="USER",
        api_key="server-key",
        current_geographic_reality=(104.0668, 30.5728),
    )

    assert state == saved[0]
    assert state.identity == "春熙路"
    assert state.status == GeographicStatus.GROUNDED.value
    assert (state.lng, state.lat) == (104.078293, 30.65744)


def test_local_area_fallback_grounds_decision_geography_in_current_city(monkeypatch) -> None:
    fallback_calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve",
        lambda *_args: GeographicResolutionResult(status="UNRESOLVED"),
    )
    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve_city_context",
        lambda *_args: "成都市",
    )

    def resolve_local_area(title: str, context: str | None, _api_key: str):
        fallback_calls.append((title, context))
        return (
            GeographicResolutionResult(status="UNRESOLVED")
            if context is None
            else GeographicResolutionResult(
                status="GROUNDED",
                geographic_identity="成都市成都高新技术产业开发区(南区)",
                geographic_precision=GeographicPrecision.AREA,
                lng=104.065546,
                lat=30.592078,
            )
        )

    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve_local_area",
        resolve_local_area,
    )
    monkeypatch.setattr(
        decision_geography_module.decision_geography_store,
        "save",
        lambda _conversation_id, state: state,
    )

    state = decision_geography_module.decision_geography_service.apply(
        "conversation-id",
        intent_established=True,
        intent_type="RELOCATE",
        identity="高新南",
        identity_source="USER",
        api_key="server-key",
        current_geographic_reality=(104.0668, 30.5728),
    )

    assert fallback_calls == [("高新南", None), ("高新南", "成都市")]
    assert state is not None
    assert state.status == GeographicStatus.GROUNDED.value
    assert (state.lng, state.lat) == (104.065546, 30.592078)


def test_local_relation_suffix_is_removed_before_resolution(monkeypatch) -> None:
    calls: list[tuple[str, str | None]] = []

    def resolve(title: str, context: str | None, _api_key: str):
        calls.append((title, context))
        return (
            GeographicResolutionResult(status="UNRESOLVED")
            if context is None
            else GeographicResolutionResult(
                status="GROUNDED",
                geographic_identity="成都市春熙路",
                geographic_precision=GeographicPrecision.STREET,
                lng=104.078293,
                lat=30.65744,
            )
        )

    monkeypatch.setattr(decision_geography_module.geographic_resolver, "resolve", resolve)
    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve_city_context",
        lambda *_args: "成都市",
    )
    monkeypatch.setattr(
        decision_geography_module.decision_geography_store,
        "save",
        lambda _conversation_id, state: state,
    )

    state = decision_geography_module.decision_geography_service.apply(
        "conversation-id",
        intent_established=True,
        intent_type="RELOCATE",
        identity="春熙路附近",
        identity_source="USER",
        api_key="server-key",
        current_geographic_reality=(104.0668, 30.5728),
    )

    assert calls == [("春熙路", None), ("春熙路", "成都市")]
    assert state is not None
    assert state.identity == "春熙路"
    assert state.status == GeographicStatus.GROUNDED.value


def test_failed_contextual_resolution_replaces_prior_decision_geography(monkeypatch) -> None:
    saved: list[DecisionGeography] = []
    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve",
        lambda *_args: GeographicResolutionResult(status="UNRESOLVED"),
    )
    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve_city_context",
        lambda *_args: "成都市",
    )
    monkeypatch.setattr(
        decision_geography_module.geographic_resolver,
        "resolve_local_area",
        lambda *_args: GeographicResolutionResult(status="UNRESOLVED"),
    )
    monkeypatch.setattr(
        decision_geography_module.decision_geography_store,
        "save",
        lambda _conversation_id, state: saved.append(state) or state,
    )

    state = decision_geography_module.decision_geography_service.apply(
        "conversation-id",
        intent_established=True,
        intent_type="RELOCATE",
        identity="高新南",
        identity_source="USER",
        api_key="server-key",
        current_geographic_reality=(104.0668, 30.5728),
    )

    assert state == saved[0]
    assert state.identity == "高新南"
    assert state.status == GeographicStatus.UNRESOLVED.value
    assert state.lng is None
    assert state.lat is None


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
