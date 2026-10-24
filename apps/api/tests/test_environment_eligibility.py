import copy
import json
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import UTC, datetime

import pytest

from app.models.conversation import ConversationMessage
from app.models.property import GeographicStatus, Property
from app.services.environment_eligibility import (
    eligible_environment,
    environment_attention_context,
)
from app.services.place_context_reality import PlaceContextRealityService, PlacePoi
from app.services.user_reality_return import UserRealityReturn


def home_with_evidence():
    home = Property(
        id="home", conversation_id="conversation", title="已确认住所",
        geographic_status=GeographicStatus.GROUNDED,
        geographic_identity="真实住所身份", lng=116.4, lat=39.9,
    )
    now = datetime.now(UTC).isoformat()
    home.place_context = [PlaceContextRealityService.admit(
        home=home, category=category,
        place=PlacePoi(identifier, name, f"真实区域 {name}", code, 116.401, 39.901, 200, now),
        walking_minutes=None, walking_evidence=None, anchor_candidate=True,
    ) for category, identifier, name, code in (
        ("TRANSIT", "station", "真实地铁站", "150500"),
        ("COMMERCIAL", "mall", "真实商场", "060101"),
    )]
    return home


def attention():
    return {
        "property_id": "home", "category": "TRANSIT",
        "type_codes": ["150500"],
        "quote": "我想了解这里的地铁", "environment_ids": ["station"],
    }


def evaluate(home, interpretation=None, **overrides):
    inputs = {
        "conversation_id": "conversation",
        "history": [ConversationMessage("user", "我想了解这里的地铁", id=42)],
        "user_text": "我想了解这里的地铁", "properties": [home],
        "focused_property_id": "home", "attention_property_id": None,
    }
    inputs.update(overrides)
    return eligible_environment(interpretation, **inputs)


def test_grounded_relevant_object_has_traceable_eligibility_without_changing_reality():
    home = home_with_evidence()
    before = copy.deepcopy(home)
    result = evaluate(home, attention())
    assert len(result) == 1
    value = asdict(result[0])
    assert value["attention"] == {
        "conversation_id": "conversation", "source_user_turn_id": 42,
        "source_quote": "我想了解这里的地铁", "property_id": "home",
        "property_identity": home.geographic_identity,
        "property_lng": home.lng, "property_lat": home.lat,
        "category": "TRANSIT", "place_binding_source": "FOCUS",
        "type_codes": ("150500",),
    }
    assert value["environment_external_id"] == "station"
    assert value["evidence"] == home.place_context[0]["evidence"]
    assert value["admission"] == home.place_context[0]["admission"]
    assert value["relevance_basis"] == "USER_EXPRESSED_CATEGORY"
    assert home == before


def test_unrelated_admitted_object_does_not_qualify():
    assert not evaluate(home_with_evidence(), {**attention(), "environment_ids": ["mall"]})


def test_metro_attention_excludes_admitted_bus_stop_even_when_its_name_contains_metro():
    home = home_with_evidence()
    bus = PlaceContextRealityService.admit(
        home=home, category="TRANSIT",
        place=PlacePoi("bus", "地铁站公交站", "真实区域 地铁站公交站", "150700",
                       116.401, 39.901, 200, datetime.now(UTC).isoformat()),
        walking_minutes=None, walking_evidence=None, anchor_candidate=False,
    )
    home.place_context.append(bus)
    result = evaluate(home, {**attention(), "environment_ids": ["station", "bus"]})
    assert [item.environment_external_id for item in result] == ["station"]
    assert not evaluate(home, {**attention(), "environment_ids": ["bus"]})
    assert not evaluate(home, {**attention(), "type_codes": []})
    assert not evaluate(home, {**attention(), "type_codes": ["unverified-kind"]})


def home_with_related_rail():
    home = home_with_evidence()
    for identifier, code in [(f"tram-{i}", "150705") for i in range(3)] + [("bus", "150700")]:
        home.place_context.append(PlaceContextRealityService.admit(
            home=home, category="TRANSIT",
            place=PlacePoi(identifier, identifier, f"区域 {identifier}", code,
                           116.401, 39.901, 200, datetime.now(UTC).isoformat()),
            walking_minutes=None, walking_evidence=None, anchor_candidate=False,
        ))
    return home


def test_metro_direct_match_and_three_tram_supplements_preserve_attention_and_evidence():
    home = home_with_related_rail()
    before = copy.deepcopy(home)
    result = evaluate(home, attention())
    assert [(item.environment_external_id, item.relevance_basis) for item in result] == [
        ("station", "USER_EXPRESSED_CATEGORY"),
        ("tram-0", "RELATED_RAIL_SUPPLEMENT"),
        ("tram-1", "RELATED_RAIL_SUPPLEMENT"),
        ("tram-2", "RELATED_RAIL_SUPPLEMENT"),
    ]
    for item in result:
        assert item.attention.type_codes == ("150500",)
        assert item.attention.source_user_turn_id == 42
        source = next(row for row in home.place_context if row["external_id"] == item.environment_external_id)
        assert asdict(item.evidence) == source["evidence"]
        assert asdict(item.admission) == source["admission"]
    assert [item.environment_type_code for item in result] == ["150500", "150705", "150705", "150705"]
    assert home == before


def test_related_rail_does_not_require_model_selected_ids_and_is_not_duplicated():
    home = home_with_related_rail()
    for ids in ([], ["tram-0"]):
        result = evaluate(home, {**attention(), "environment_ids": ids})
        assert [item.environment_external_id for item in result] == ["tram-0", "tram-1", "tram-2"]
        assert all(item.relevance_basis == "RELATED_RAIL_SUPPLEMENT" for item in result)


def test_supplements_require_current_metro_attention_and_same_place_admission():
    home = home_with_related_rail()
    for signal in (None, {**attention(), "quote": "未表达的关注"}):
        assert not evaluate(home, signal)
    assert not evaluate(home, {**attention(), "environment_ids": []}, focused_property_id="other")
    # No implicit all-TRANSIT expansion for a Bus request.
    bus_result = evaluate(home, {**attention(), "type_codes": ["150700"], "environment_ids": ["bus"]})
    assert [item.environment_external_id for item in bus_result] == ["bus"]
    home.place_context[2].pop("evidence")
    home.place_context[3]["admission"]["property_id"] = "other-place"
    home.place_context[4]["structure_version"] = 2
    assert not evaluate(home, {**attention(), "environment_ids": []})


@pytest.mark.parametrize("interpretation", [None, {}, {**attention(), "quote": "模型补造的关注"}])
def test_no_explicit_attention_does_not_qualify(interpretation):
    assert not evaluate(home_with_evidence(), interpretation)


@pytest.mark.parametrize("field", ["evidence", "admission"])
def test_missing_admitted_evidence_does_not_qualify(field):
    home = home_with_evidence()
    home.place_context[0].pop(field)
    assert not evaluate(home, attention())
    assert len(environment_attention_context([home])[0]["places"]) == 1


def test_cross_place_evidence_does_not_qualify():
    home = home_with_evidence()
    other = replace(home, id="other", geographic_identity="另一个住所")
    assert not evaluate(other, {**attention(), "property_id": "other"}, focused_property_id="other")
    assert not evaluate(replace(home, conversation_id="other-conversation"), attention())
    assert not evaluate(home, attention(), conversation_id="other-conversation")


@pytest.mark.parametrize("overrides", [
    {"focused_property_id": None},
    {"focused_property_id": "other"},
    {"attention_property_id": "other"},
    {"history": [ConversationMessage("user", "我想了解这里的地铁")]},
    {"history": [ConversationMessage("assistant", "我想了解这里的地铁", id=42)]},
    {"history": [ConversationMessage("user", "我想了解这里的地铁", id=42),
                 ConversationMessage("user", "不用看地铁了", id=43)]},
])
def test_focus_and_current_user_turn_are_required(overrides):
    assert not evaluate(home_with_evidence(), attention(), **overrides)


def test_existing_user_attention_can_bind_place_without_map_focus():
    result = evaluate(home_with_evidence(), attention(), focused_property_id=None,
                      attention_property_id="home")
    assert result[0].attention.place_binding_source == "USER_ATTENTION"


def test_legacy_duplicate_and_unresolved_evidence_fail_closed():
    home = home_with_evidence()
    home.place_context[0]["structure_version"] = 2
    assert not evaluate(home, attention())
    home = home_with_evidence()
    home.place_context.append(copy.deepcopy(home.place_context[0]))
    assert not evaluate(home, attention())
    home = home_with_evidence()
    home.geographic_status = GeographicStatus.UNRESOLVED
    assert not evaluate(home, attention())


@pytest.mark.parametrize("use_focus", [True, False])
def test_existing_expression_interpretation_supplies_attention_with_one_model_call(use_focus):
    home = home_with_evidence()

    class Intelligence:
        calls = 0
        signal = attention()

        def generate_json(self, prompt, **kwargs):
            self.calls += 1
            assert "Admitted environment candidates:" in prompt
            assert '"external_id": "station"' in prompt
            return json.dumps({
                "claim_nature": "OTHER", "reality_type": None, "claim_quote": None,
                "property_id": None, "binding_evidence": None, "binding_source": None,
                "attention_property_id": None if use_focus else home.id,
                "attention_evidence": None if use_focus else "我想住已确认住所",
                "environment_attention": self.signal,
            })

    intelligence = Intelligence()
    service = UserRealityReturn(intelligence=intelligence)
    history = [ConversationMessage("user", "我想住已确认住所", id=40),
               ConversationMessage("user", "我想了解这里的地铁", id=42)]
    result = service.resolve_expression(history, [home], history[-1].content,
                                        focused_property_id=home.id if use_focus else None,
                                        conversation_id=home.conversation_id)
    assert intelligence.calls == 1
    assert len(result.environment_eligibility) == 1
    assert result.property_id is None and result.attention_property_id is None
    # Same grounded place + ordinary conversation is not environment attention.
    intelligence.signal = None
    result = service.resolve_expression(history, [home], history[-1].content,
                                        focused_property_id=home.id,
                                        conversation_id=home.conversation_id)
    assert intelligence.calls == 2
    assert result.environment_eligibility == ()


@pytest.mark.parametrize("has_evidence", [True, False])
def test_eligibility_travels_through_existing_runtime_and_sse(monkeypatch, has_evidence):
    from app.api.chat import _stream_events
    from app.models.profile_analysis import ProfileAnalysis
    from app.models.profile_patch import LivingProfilePatch
    from app.services.chat_service import ChatService
    from app.services.user_reality_return import PropertyExpressionResolution

    recorded = []
    from app.services.conversation_manager import conversation_manager
    monkeypatch.setattr(conversation_manager, "record_environment_attention",
                        lambda *args: recorded.append(args))
    items = evaluate(home_with_evidence(), attention()) if has_evidence else ()
    profile = Future()
    profile.set_result(ProfileAnalysis(patch=LivingProfilePatch()))
    service = ChatService()
    monkeypatch.setattr(service, "_update_profile", lambda **kwargs: ())
    monkeypatch.setattr(service, "_stream_assistant_reply", lambda *args: iter(["正常回复"]))
    with ThreadPoolExecutor(max_workers=1) as executor:
        chunks = service._complete_stream_turn(
            "conversation", [ConversationMessage("user", "我想了解这里的地铁", id=42)],
            None, profile, executor, False, None, current_user_turn_id=42,
            property_resolution=PropertyExpressionResolution(environment_eligibility=items),
        )
        frames = list(_stream_events(chunks))
    event = next(frame for frame in frames if frame.startswith("event: world-consequence-ready"))
    payload = json.loads(event.split("data: ", 1)[1])
    assert payload == {"environment_eligibility": {
        "conversation_id": "conversation", "source_user_turn_id": 42,
        "items": [json.loads(json.dumps(asdict(item))) for item in items],
    }}
    assert recorded[0][:2] == ("conversation", 42)
    assert bool(recorded[0][2]) is has_evidence
    assert any('正常回复' in frame or r'\u6b63' in frame for frame in frames)


def test_resume_revalidates_current_attention_and_does_not_replay_a_cached_grant():
    from app.models.environment_eligibility import EnvironmentEligibilityResult
    from app.services.environment_eligibility import (
        environment_attention_snapshot,
        resume_environment_eligibility,
    )

    home = home_with_evidence()
    original = EnvironmentEligibilityResult("conversation", 42, evaluate(home, attention()))
    turn = ConversationMessage("user", "我想了解这里的地铁", id=42,
                               environment_attention=environment_attention_snapshot(original))
    history = [turn, ConversationMessage("assistant", "回复", id=43)]
    assert resume_environment_eligibility("conversation", history, [home]) == original
    # Current evidence, not a stored Eligibility snapshot, remains authoritative.
    home.place_context[0]["admission"]["status"] = "REJECTED"
    assert not resume_environment_eligibility("conversation", history, [home]).items
    assert not resume_environment_eligibility("conversation", [], [home])


@pytest.mark.parametrize("mutation", ["no_attention", "new_turn", "cross_place", "cross_turn", "quote", "coordinates", "types"])
def test_resume_fails_closed_for_missing_stale_or_mismatched_attention(mutation):
    from app.models.environment_eligibility import EnvironmentEligibilityResult
    from app.services.environment_eligibility import (
        environment_attention_snapshot,
        resume_environment_eligibility,
    )

    home = home_with_evidence()
    result = EnvironmentEligibilityResult("conversation", 42, evaluate(home, attention()))
    snapshot = environment_attention_snapshot(result)
    turn = ConversationMessage("user", "我想了解这里的地铁", id=42, environment_attention=snapshot)
    history = [turn]
    if mutation == "no_attention":
        turn.environment_attention = None
    elif mutation == "new_turn":
        history.append(ConversationMessage("user", "换个话题", id=44))
    elif mutation == "cross_place":
        snapshot["attention"]["property_id"] = "another"
    elif mutation == "cross_turn":
        snapshot["attention"]["source_user_turn_id"] = 40
    elif mutation == "quote":
        snapshot["attention"]["source_quote"] = "并非用户说的话"
    elif mutation == "coordinates":
        home.lng += 0.01
    elif mutation == "types":
        snapshot["attention"]["type_codes"] = 12
    assert not resume_environment_eligibility("conversation", history, [home]).items


def test_resume_rail_supplements_use_current_evidence_without_bus_or_provider_calls():
    from app.models.environment_eligibility import EnvironmentEligibilityResult
    from app.services.environment_eligibility import (
        environment_attention_snapshot,
        resume_environment_eligibility,
    )

    home = home_with_evidence()
    now = datetime.now(UTC).isoformat()
    for i, code in enumerate(["150705"] * 3 + ["150700"] * 17):
        home.place_context.append(PlaceContextRealityService.admit(
            home=home, category="TRANSIT",
            place=PlacePoi(f"rail-{i}", f"站点{i}", f"区域 站点{i}", code, 116.401, 39.901, 200, now),
            walking_minutes=None, walking_evidence=None, anchor_candidate=False,
        ))
    original = EnvironmentEligibilityResult("conversation", 42, evaluate(home, attention()))
    turn = ConversationMessage("user", "我想了解这里的地铁", id=42,
                               environment_attention=environment_attention_snapshot(original))
    resumed = resume_environment_eligibility("conversation", [turn], [home])
    assert resumed == original
    assert [item.environment_type_code for item in resumed.items] == ["150500"] + ["150705"] * 3
    assert {item.attention.source_user_turn_id for item in resumed.items} == {42}
