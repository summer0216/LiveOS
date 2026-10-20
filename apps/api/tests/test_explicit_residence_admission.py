from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.conversation import ConversationMessage
from app.models.decision_geography import DecisionGeography
from app.models.geographic_clarification import GeographicClarification
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus, Property
from app.services.chat_service import (
    STREAM_KEEP_ALIVE,
    WORLD_CONSEQUENCE_READY,
    ChatService,
    WorldStateReady,
    _admit_current_residence,
)
from app.services.geographic_resolution import (
    GeographicPlaceCandidate,
    GeographicResolutionResult,
)
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.services.user_reality_return import PropertyExpressionResolution
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation

GEOGRAPHY = DecisionGeography(
    intent_established=True, intent_type="residence", identity="明城市新区清园东区",
    identity_source="USER", source_user_turn_id=123, status="GROUNDED",
    geographic_scope="LOCAL", geographic_precision=GeographicPrecision.PLACE,
    geographic_identity="明城市新区清园东区", lng=116.3, lat=39.6,
)
CANDIDATE = GeographicPlaceCandidate(
    provider_id="provider-east", name="清园东区", city="明城市", district="新区",
    category="商务住宅;住宅区;住宅小区", lng=116.3, lat=39.6,
)
EVIDENCE = GeographicResolutionResult(
    status="GROUNDED", geographic_identity=GEOGRAPHY.geographic_identity,
    geographic_precision=GeographicPrecision.PLACE, geographic_scope="LOCAL",
    lng=116.3, lat=39.6, candidates=(CANDIDATE,),
)


@pytest.fixture
def residence(monkeypatch):
    cid = uuid_for("independent-residence")
    create_owned_conversation(TestClient(app), cid)
    calls = []
    monkeypatch.setattr(
        "app.services.chat_service.decision_geography_service.city_context",
        lambda *_: "明城市",
    )

    def resolve(*args):
        calls.append(args)
        return EVIDENCE

    monkeypatch.setattr(
        "app.services.chat_service.geographic_resolver.resolve_local_area", resolve,
    )
    return cid, calls


@pytest.mark.parametrize("changes", [
    {"intent_type": "work_location"}, {"intent_type": "travel"},
    {"intent_type": "query"}, {"intent_type": "housing_search"},
    {"intent_established": False}, {"identity_source": "INFERRED"},
    {"source_user_turn_id": 122}, {"source_user_turn_id": None},
    {"status": "UNRESOLVED"}, {"geographic_scope": "CITY"},
    {"geographic_precision": GeographicPrecision.AREA},
    {"geographic_identity": None}, {"lng": None}, {"lng": float("nan")},
    {"lat": 91},
])
def test_non_current_residence_never_starts_early_grounding(residence, changes):
    cid, calls = residence
    assert _admit_current_residence(cid, replace(GEOGRAPHY, **changes), 123) is None
    assert calls == []
    assert property_manager.list(cid) == []


@pytest.mark.parametrize("evidence", [
    replace(EVIDENCE, status="UNRESOLVED"),
    replace(EVIDENCE, ambiguous=True),
    replace(EVIDENCE, candidates=(CANDIDATE, replace(CANDIDATE, provider_id="other"))),
    replace(EVIDENCE, candidates=()),
    replace(EVIDENCE, geographic_identity="明城市新区另一处"),
    replace(EVIDENCE, lng=116.4),
    replace(EVIDENCE, candidates=(replace(CANDIDATE, provider_id=""),)),
])
def test_provider_ambiguity_or_identity_conflict_creates_no_property(
    monkeypatch, residence, evidence,
):
    cid, _ = residence
    monkeypatch.setattr(
        "app.services.chat_service.geographic_resolver.resolve_local_area",
        lambda *_: evidence,
    )
    assert _admit_current_residence(cid, GEOGRAPHY, 123) is None
    assert property_manager.list(cid) == []


@pytest.mark.parametrize("title", [CANDIDATE.name, GEOGRAPHY.identity])
def test_later_profile_reuses_home_and_cannot_overwrite_identity(residence, title):
    cid, calls = residence
    admitted = _admit_current_residence(cid, GEOGRAPHY, 123)
    assert admitted is not None
    home, _ = admitted
    analysis = ProfileAnalysis(
        patch=LivingProfilePatch(budget=6000, commute_minutes=30),
        choices=[Property(title=title, district="新区", rent=5000, area=80,
                          bedrooms=2, bathrooms=1, pet_friendly=False)],
        geographic_clarification=GeographicClarification(
            relevant=True, target_property_id=home.id,
            geographic_identity="错误地点", geographic_precision=GeographicPrecision.PLACE,
            lng=117, lat=40,
        ),
    )
    ChatService()._update_profile(
        cid, [ConversationMessage(role="user", content="我想住在明城市新区清园东区")],
        analysis=analysis, apply_decision_geography=False,
        current_decision_geography=GEOGRAPHY, admitted_residence=admitted,
    )
    homes = property_manager.list(cid)
    assert len(homes) == 1
    assert homes[0].id == home.id
    assert homes[0].geographic_identity == GEOGRAPHY.geographic_identity
    assert (homes[0].lng, homes[0].lat) == (GEOGRAPHY.lng, GEOGRAPHY.lat)
    assert (homes[0].rent, homes[0].area, homes[0].bedrooms, homes[0].bathrooms) == (5000, 80, 2, 1)
    assert homes[0].pet_friendly is False
    assert len(calls) == 1
    profile = profile_manager.get(cid)
    assert profile.budget == 6000
    assert profile.commute_minutes == 30
    ChatService()._update_profile(
        cid, [ConversationMessage(role="user", content="预算暂时不明确")],
        analysis=ProfileAnalysis(patch=LivingProfilePatch(clear_fields=frozenset({"budget"}))),
        apply_decision_geography=False, current_decision_geography=GEOGRAPHY,
        admitted_residence=admitted,
    )
    assert profile_manager.get(cid).budget is None
    assert profile_manager.get(cid).commute_minutes == 30


def test_stream_admits_before_profile_future_and_then_finishes_profile(monkeypatch, residence):
    cid, _ = residence
    service = ChatService()
    profile = Future()
    monkeypatch.setattr("app.services.chat_service.DISCOVERY_KEEP_ALIVE_SECONDS", 0.001)
    monkeypatch.setattr(
        "app.services.chat_service.user_reality_return.resolve_expression",
        lambda *a, **kw: PropertyExpressionResolution(),
    )
    monkeypatch.setattr(service, "_stream_assistant_reply", lambda *a: iter(["reply"]))
    history = [ConversationMessage(role="user", content="我想住在明城市新区清园东区")]
    with ThreadPoolExecutor(max_workers=2) as executor:
        stream = service._complete_stream_turn(
            cid, history, None, profile, executor, True, GEOGRAPHY,
            current_user_turn_id=123,
        )
        try:
            assert isinstance(next(stream), WorldStateReady)
            assert next(stream) is WORLD_CONSEQUENCE_READY
            assert not profile.done()
            assert property_manager.list(cid)[0].geographic_status == GeographicStatus.GROUNDED
            assert next(stream) is STREAM_KEEP_ALIVE
            profile.set_result(ProfileAnalysis(
                patch=LivingProfilePatch(budget=6000), choices=[Property(title=GEOGRAPHY.identity)],
            ))
            assert list(stream)[-1] == "reply"
            assert len(property_manager.list(cid)) == 1
            assert profile_manager.get(cid).budget == 6000
        finally:
            stream.close()
            if not profile.done():
                profile.set_result(ProfileAnalysis(patch=LivingProfilePatch()))


def test_existing_grounded_identity_is_reused_or_protected(residence):
    cid, _ = residence
    original = _admit_current_residence(cid, GEOGRAPHY, 123)
    assert original is not None
    again = _admit_current_residence(cid, GEOGRAPHY, 123)
    assert again is not None and again[0].id == original[0].id
    property_manager.update_geographic_grounding(
        original[0].id, cid, geographic_identity="另一身份",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED, lng=117, lat=40,
    )
    assert _admit_current_residence(cid, GEOGRAPHY, 123) is None
    assert property_manager.list(cid)[0].geographic_identity == "另一身份"


def test_non_residence_stream_keeps_the_profile_choice_path(monkeypatch, residence):
    cid, calls = residence
    profile = Future()
    profile.set_result(ProfileAnalysis(
        patch=LivingProfilePatch(budget=6000), choices=[Property(title="用户已有候选")],
    ))
    service = ChatService()
    updates = []
    monkeypatch.setattr(service, "_update_profile", lambda **kw: updates.append(kw) or ())
    monkeypatch.setattr(service, "_stream_assistant_reply", lambda *a: iter(["reply"]))
    monkeypatch.setattr(
        "app.services.chat_service.user_reality_return.resolve_expression",
        lambda *a, **kw: PropertyExpressionResolution(),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert list(service._complete_stream_turn(
            cid, [ConversationMessage(role="user", content="我在清园东区工作")],
            None, profile, executor, True, replace(GEOGRAPHY, intent_type="work_location"),
            current_user_turn_id=123,
        ))[-1] == "reply"
    assert calls == []
    assert "admitted_residence" not in updates[0]
    assert updates[0]["analysis"].choices[0].title == "用户已有候选"
