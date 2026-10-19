from dataclasses import replace
from uuid import uuid4

import pytest

from app.models.decision_geography import DecisionGeography
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus, Property
from app.services import decision_geography_service as module
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.geographic_resolution import GeographicResolutionResult
from app.services.property_manager import property_manager


@pytest.fixture
def geography(monkeypatch):
    state = DecisionGeography(
        intent_established=True, intent_type="residence", identity="龙湖时代天街",
        identity_source="USER", source_user_turn_id=1,
    )
    calls = []

    def resolve(identity, context, key):
        calls.append((identity, context))
        if identity in ("成都", "成都市"):
            return GeographicResolutionResult(
                status="GROUNDED", geographic_scope="CITY",
                geographic_identity="四川省成都市", lng=104.06, lat=30.67,
            )
        if identity == state.identity:
            if context == "四川省成都市":
                return GeographicResolutionResult(
                    status="GROUNDED", geographic_scope="LOCAL",
                    geographic_identity="四川省成都市郫都区龙湖·时代天街",
                    geographic_precision=GeographicPrecision.PLACE,
                    lng=103.920730, lat=30.753792,
                )
            return GeographicResolutionResult(status="UNRESOLVED", ambiguous=True)
        return GeographicResolutionResult(status="UNRESOLVED")

    monkeypatch.setattr(module.geographic_resolver, "resolve", resolve)
    monkeypatch.setattr(module.geographic_resolver, "resolve_local_area",
                        lambda *args: GeographicResolutionResult(status="UNRESOLVED"))
    monkeypatch.setattr(module.decision_geography_service, "get", lambda _: state)
    monkeypatch.setattr(module.decision_geography_store, "save", lambda _, value: value)
    return state, calls


def test_ambiguity_cannot_use_current_world_city(monkeypatch, geography):
    state, _ = geography
    monkeypatch.setattr(module.decision_geography_service, "_current_city_context",
                        lambda *args: pytest.fail("Must ask for explicit city"))
    result = module.decision_geography_service.apply(
        "conversation", intent_established=True, intent_type=state.intent_type,
        identity=state.identity, identity_source="USER", api_key="key",
        current_geographic_reality=(116.4, 39.9),
    )
    assert result.status == "UNRESOLVED"
    assert result.lng is None and result.geographic_identity is None


def test_city_answer_reuses_original_place_and_strict_admission(geography):
    state, calls = geography
    signal = module.decision_geography_service.city_answer_signal("conversation", "成都", "key")
    assert signal.identity == "成都的龙湖时代天街"
    assert signal.intent_type == state.intent_type
    result = module.decision_geography_service.apply(
        "conversation", intent_established=signal.intent_established,
        intent_type=signal.intent_type, identity=signal.identity,
        identity_source=signal.identity_source, api_key="key", source_user_turn_id=2,
    )
    assert (state.identity, "四川省成都市") in calls
    assert result.status == "GROUNDED"
    assert result.source_user_turn_id == 2
    assert (result.lng, result.lat) == (103.920730, 30.753792)


@pytest.mark.parametrize("answer", ["我在成都工作", "不知道", "随便", "成都天气怎么样"])
def test_non_city_answers_do_not_supply_residential_context(geography, answer):
    assert module.decision_geography_service.city_answer_signal("conversation", answer, "key") is None


def test_provider_failure_cannot_establish_city(monkeypatch, geography):
    monkeypatch.setattr(module.geographic_resolver, "resolve",
                        lambda *args: GeographicResolutionResult(status="UNRESOLVED"))
    assert module.decision_geography_service.city_answer_signal("conversation", "成都", "key") is None


def test_city_question_is_persisted_in_existing_conversation(monkeypatch, geography):
    replies = []
    monkeypatch.setattr(conversation_manager, "append_assistant_message",
                        lambda cid, text: replies.append((cid, text)))
    chunks = list(chat_service._stream_assistant_reply("conversation", []))
    assert chunks == ["“龙湖时代天街”有多个同名地点。你指的是哪个城市？"]
    assert replies == [("conversation", chunks[0])]


def test_no_pending_ambiguity_means_no_city_binding(monkeypatch, geography):
    state, _ = geography
    monkeypatch.setattr(module.decision_geography_service, "get",
                        lambda _: replace(state, status="GROUNDED"))
    assert module.decision_geography_service.city_answer_signal("conversation", "成都", "key") is None


def test_city_answer_retries_existing_choice_without_restatement(monkeypatch, geography):
    state, calls = geography
    cid = str(uuid4())
    conversation_manager.get_or_create(cid)
    home = property_manager.materialize_choices(cid, [Property(title=state.identity)])[0]
    monkeypatch.setattr(module.decision_geography_service, "city_context", lambda *args: "四川省成都市")
    monkeypatch.setattr(module.geographic_resolver, "resolve_local_area",
                        lambda title, context, key: module.geographic_resolver.resolve(state.identity, context, key))
    grounded = replace(
        state, identity="成都的龙湖时代天街", status="GROUNDED",
        geographic_scope="LOCAL", lng=103.920730, lat=30.753792,
        geographic_identity="四川省成都市郫都区龙湖·时代天街",
    )
    chat_service._update_profile(
        cid, [], analysis=ProfileAnalysis(patch=LivingProfilePatch()),
        apply_decision_geography=False, current_decision_geography=grounded,
    )
    restored = property_manager.get_scoped(home.id, cid)
    assert (state.identity, "四川省成都市") in calls
    assert restored.geographic_status == GeographicStatus.GROUNDED
    assert restored.geographic_identity == "四川省成都市郫都区龙湖·时代天街"
    assert len(property_manager.list(cid)) == 1


@pytest.mark.parametrize("identity", [
    "北京市的大兴区龙湖时代天街东区",
    "北京市大兴区龙湖时代天街东区",
])
@pytest.mark.parametrize("resolution", ["matching", "ambiguous", "different_place", "missing_coordinates"])
def test_confirmed_identity_reuses_admission_without_expression_format(monkeypatch, identity, resolution):
    cid = str(uuid4())
    conversation_manager.get_or_create(cid)
    original, east, west = property_manager.materialize_choices(cid, [
        Property(title="龙湖时代天街"), Property(title="龙湖时代天街东区"),
        Property(title="龙湖时代天街西区"),
    ])
    canonical = "北京市大兴区龙湖时代天街东区"
    grounded = DecisionGeography(
        intent_established=True, intent_type="residence", identity=identity,
        identity_source="USER", status="GROUNDED", geographic_scope="LOCAL",
        geographic_identity=canonical, geographic_precision=GeographicPrecision.PLACE,
        lng=116.323739, lat=39.686403, source_user_turn_id=42,
    )
    calls = []

    def resolve(title, context, key):
        calls.append((title, context))
        assert title == canonical
        if resolution == "ambiguous":
            return GeographicResolutionResult(status="UNRESOLVED", ambiguous=True)
        return GeographicResolutionResult(
            status="GROUNDED", geographic_scope="LOCAL",
            geographic_identity=canonical if resolution != "different_place" else "另一个地点",
            geographic_precision=GeographicPrecision.PLACE,
            lng=116.0 if resolution == "different_place" else (
                None if resolution == "missing_coordinates" else grounded.lng),
            lat=grounded.lat,
        )

    monkeypatch.setattr(module.decision_geography_service, "city_context", lambda *args: "北京市")
    monkeypatch.setattr(module.geographic_resolver, "resolve_local_area", resolve)
    # No restated choice: this exercises association with already persisted homes.
    chat_service._update_profile(
        cid, [], analysis=ProfileAnalysis(patch=LivingProfilePatch()),
        apply_decision_geography=False, current_decision_geography=grounded,
    )
    restored = property_manager.get_scoped(east.id, cid)
    if resolution == "matching":
        assert restored.geographic_status == GeographicStatus.GROUNDED
        assert restored.geographic_identity == canonical
        assert (restored.lng, restored.lat) == (grounded.lng, grounded.lat)
    else:
        assert restored.geographic_status == GeographicStatus.UNRESOLVED
        assert restored.geographic_identity is None
    assert property_manager.get_scoped(original.id, cid).geographic_status == restored.geographic_status
    assert property_manager.get_scoped(west.id, cid).geographic_status == GeographicStatus.UNRESOLVED
    assert calls == [(canonical, "北京市"), (canonical, "北京市")]
    assert len(property_manager.list(cid)) == 3
