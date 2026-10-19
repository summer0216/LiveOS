from dataclasses import asdict
from uuid import uuid4

import pytest

from app.core.config import settings
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus, Property
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_geography_service import decision_geography_service
from app.services.geographic_resolution import geographic_resolver
from app.services.property_manager import property_manager


def poi(**changes):
    return {"id": "provider-east", "name": "云杉花园东区", "cityname": "杭州市",
            "adname": "西湖区", "type": "商务住宅;住宅区;住宅小区",
            "location": "120.1,30.2", "address": "云杉路8号", "adcode": "330106", **changes}


class Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def provider(monkeypatch, rows, count=None):
    calls = []

    def get(url, *, params, timeout):
        calls.append((url, params))
        return Response({"status": "1", "pois": rows,
                         **({"count": str(count)} if count is not None else {})})

    monkeypatch.setattr("httpx.get", get)
    return calls


@pytest.mark.parametrize("category", ["商务住宅;住宅区;住宅小区", "购物服务;商场;购物中心"])
def test_unique_place_preserves_provider_evidence_and_uses_place_precision(monkeypatch, category):
    calls = provider(monkeypatch, [poi(type=category)])
    result = geographic_resolver.resolve_local_area("云杉花园东区", "杭州市", "key")
    assert result.status == "GROUNDED"
    assert result.geographic_identity == "杭州市西湖区云杉花园东区"
    assert result.geographic_precision == GeographicPrecision.PLACE
    assert result.geographic_scope == "LOCAL"
    assert (result.lng, result.lat) == (120.1, 30.2)
    assert asdict(result.candidates[0]) == {
        "provider_id": "provider-east", "name": "云杉花园东区", "city": "杭州市",
        "district": "西湖区", "category": category, "lng": 120.1, "lat": 30.2,
        "address": "云杉路8号", "adcode": "330106", "provider": "AMAP",
    }
    assert calls[0][1]["city"] == "杭州市"
    assert calls[0][1]["citylimit"] == "true"


@pytest.mark.parametrize("category", ["商务住宅;住宅区;住宅小区", "购物服务;商场;购物中心"])
def test_multiple_places_never_use_order_distance_or_default_subdivision(monkeypatch, category):
    rows = [poi(type=category), poi(id="provider-west", name="云杉花园西区", type=category, location="120.2,30.3")]
    for ordered in (rows, rows[::-1]):
        provider(monkeypatch, ordered)
        result = geographic_resolver.resolve_local_area("云杉花园", "杭州市", "key")
        assert result.status == "UNRESOLVED" and result.ambiguous
        assert result.lng is None and result.geographic_identity is None
        assert {c.provider_id for c in result.candidates} == {"provider-east", "provider-west"}


@pytest.mark.parametrize("changes", [
    {"id": None}, {"name": None}, {"cityname": None}, {"adname": None},
    {"location": None}, {"location": "nan,30"}, {"location": "181,30"},
    {"location": "120,91"}, {"location": "120"}, {"cityname": "苏州市"},
    {"name": "云杉花园东区停车场", "type": "交通设施服务;停车场;公共停车场"},
    {"name": "无关地点"},
])
def test_missing_identity_invalid_coordinates_and_city_conflicts_are_not_admitted(monkeypatch, changes):
    provider(monkeypatch, [poi(**changes)])
    result = geographic_resolver.resolve_local_area("云杉花园东区", "杭州市", "key")
    assert result.status == "UNRESOLVED"
    assert result.lng is None


def test_no_candidates_incomplete_evidence_and_conflicting_provider_id_stay_unresolved(monkeypatch):
    for rows in [[], [poi(), poi(id=None)], [poi(), poi(location="120.2,30.3")]]:
        provider(monkeypatch, rows)
        assert geographic_resolver.resolve_local_area("云杉花园东区", "杭州市", "key").status == "UNRESOLVED"


def test_pagination_does_not_admit_first_page_as_unique(monkeypatch):
    calls = []

    def get(url, *, params, timeout):
        calls.append(params["page"])
        return Response({"status": "1", "count": "2", "pois": [
            poi() if params["page"] == 1 else poi(id="provider-west", name="云杉花园西区"),
        ]})

    monkeypatch.setattr("httpx.get", get)
    result = geographic_resolver.resolve_local_area("云杉花园", "杭州市", "key")
    assert calls == [1, 2]
    assert result.status == "UNRESOLVED" and result.ambiguous


@pytest.mark.parametrize("explicit_identity", [None, "杭州市西湖区云杉花园"])
def test_city_then_specific_place_confirmation_reuses_original_reality_admission(monkeypatch, explicit_identity):
    monkeypatch.setattr(settings, "AMAP_WEB_SERVICE_KEY", "key")
    monkeypatch.setattr("app.services.chat_service.ai_runtime.chat_stream",
                        lambda *args: pytest.fail("Candidate clarification must not call AI"))
    east, west = poi(), poi(id="provider-west", name="云杉花园西区", location="120.2,30.3")

    def get(url, *, params, timeout):
        if url.endswith("/regeo"):
            return Response({"status": "1", "regeocode": {"addressComponent": {
                "province": "浙江省", "city": "杭州市", "district": "西湖区",
            }}})
        if url.endswith("/geo"):
            return Response({"status": "1", "geocodes": [{
                "formatted_address": "杭州市", "province": "浙江省", "city": "杭州市",
                "level": "市", "location": "120.15,30.28",
            }] if params["address"] in ("杭州", "杭州市") else []})
        return Response({"status": "1", "pois": [east] if "东区" in params["keywords"] else [east, west]})

    monkeypatch.setattr("httpx.get", get)
    cid = str(uuid4())
    conversation_manager.get_or_create(cid)
    identity = explicit_identity or "云杉花园"
    home = property_manager.materialize_choices(cid, [Property(title=identity)])[0]
    initial = decision_geography_service.apply(
        cid, intent_established=True, intent_type="residence", identity=identity,
        identity_source="USER", api_key="key",
    )
    assert initial.status == "UNRESOLVED"
    if explicit_identity:
        state = initial
    else:
        assert "哪个城市" in decision_geography_service.clarification_question(initial, "key")
        signal = decision_geography_service.city_answer_signal(cid, "杭州", "key")
        state = decision_geography_service.apply(
            cid, intent_established=True, intent_type="residence", identity=signal.identity,
            identity_source="USER", api_key="key",
        )
    assert state.status == "UNRESOLVED"
    question = next(chat_service._stream_assistant_reply(cid, []))
    assert "云杉花园东区" in question and "云杉花园西区" in question
    assert "哪个城市" not in question
    assert decision_geography_service.city_answer_signal(cid, "随便一个", "key") is None
    assert decision_geography_service.city_answer_signal(cid, "花园", "key") is None
    signal = decision_geography_service.city_answer_signal(cid, "东区", "key")
    confirmed = decision_geography_service.apply(
        cid, intent_established=True, intent_type="residence", identity=signal.identity,
        identity_source="USER", api_key="key",
    )
    assert confirmed.status == "GROUNDED"
    assert confirmed.geographic_identity == "杭州市西湖区云杉花园东区"
    chat_service._update_profile(
        cid, [], analysis=ProfileAnalysis(patch=LivingProfilePatch()),
        apply_decision_geography=False, current_decision_geography=confirmed,
    )
    restored = property_manager.get_scoped(home.id, cid)
    assert restored.geographic_status == GeographicStatus.GROUNDED
    assert restored.geographic_identity == confirmed.geographic_identity
    assert (restored.lng, restored.lat) == (120.1, 30.2)
    assert len(property_manager.list(cid)) == 1
