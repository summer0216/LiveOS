from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.property import (
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
)
from app.models.reality_evidence import RealityAdmission, RealityEvidence
from app.services.place_context_reality import (
    PlaceContextRealityService,
    PlacePoi,
    _parse_place,
    is_admitted_nearby_reality,
)
from app.services.property_manager import property_manager
from app.services.transit_duration import TransitDurationService
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_focused_user_home_persists_bounded_provider_grounded_place_context(monkeypatch):
    class Response:
        def __init__(self, pois):
            self.pois = pois

        def raise_for_status(self):
            return None

        def json(self):
            return {"status": "1", "pois": self.pois}

    def poi(identity, name, typecode, location, distance):
        return {
            "id": identity, "name": name, "typecode": typecode,
            "location": location, "distance": distance,
            "cityname": "成都市", "adname": "高新区",
        }

    def fake_get(_url, *, params, **_kwargs):
        types = params["types"]
        if types == "060101":
            return Response([
                poi("shop", "普通商户", "060100", "104.075,30.669", "30"),
                poi("mall", "真实购物中心", "060101", "104.077,30.670", "350"),
                poi("mall-2", "另一购物中心", "060101", "104.079,30.670", "600"),
            ])
        if types == "150500|150700|150705":
            return Response([
                poi("entrance", "站口", "150501", "104.075,30.669", "50"),
                poi("station", "真实地铁站", "150500", "104.078,30.671", "500"),
            ])
        if types == "141201|141202|141203":
            return Response([
                poi("university", "真实高校", "141201", "104.078,30.672", "650"),
            ])
        return Response([
            poi("unverified", "无身份学校", "141201", "invalid", "40"),
        ])

    class Walking:
        def calculate_walking_minutes(self, **kwargs):
            assert (kwargs["origin_lng"], kwargs["origin_lat"]) == (104.074, 30.668)
            return 5 if kwargs["destination_lng"] == 104.077 else 8

    client = TestClient(app)
    conversation_id = uuid_for("place-context-user-home")
    create_owned_conversation(client, conversation_id)
    home = property_manager.create(conversation_id, Property(
        title="用户指定住宅",
        geographic_identity="真实住宅地点",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=104.074,
        lat=30.668,
        provenance=PropertyProvenance.USER_PROVIDED,
        grocery_external_id="grocery",
        grocery_name="已核实超市",
        grocery_identity="成都市 已核实超市",
        grocery_lng=104.075,
        grocery_lat=30.669,
        grocery_walking_minutes=3,
    ))
    monkeypatch.setattr("app.services.place_context_reality.httpx.get", fake_get)

    result = PlaceContextRealityService(transit=Walking()).establish(
        conversation_id, home.id or "", "test-amap-key",
    )

    assert result.status == "UPDATED"
    stored = property_manager.get_scoped(home.id or "", conversation_id)
    assert stored is not None
    assert stored.place_context is not None
    assert [(item["category"], item["external_id"]) for item in stored.place_context] == [
        ("COMMERCIAL", "mall"), ("COMMERCIAL", "mall-2"),
        ("TRANSIT", "station"),
        ("EDUCATION", "university"),
    ]
    assert len(stored.place_context) <= 9
    assert all(item["structure_version"] == 3 for item in stored.place_context)
    assert all(item["name"] and item["identity"] and item["lng"] and item["lat"] for item in stored.place_context)
    for item in stored.place_context:
        evidence = item["evidence"]
        admission = item["admission"]
        assert evidence["source_provider"] == "AMAP"
        assert evidence["source_reference"] == PlaceContextRealityService.endpoint
        assert evidence["source_record_id"] == item["external_id"]
        assert evidence["identity"] == item["identity"]
        assert RealityEvidence.from_mapping(evidence).qualifies()
        assert admission["status"] == "ADMITTED"
        assert admission["property_id"] == home.id
        assert admission["property_identity"] == home.geographic_identity
        assert RealityAdmission.from_mapping(admission).qualifies_for(
            property_id=home.id or "",
            property_identity=home.geographic_identity or "",
            property_lng=home.lng or 0,
            property_lat=home.lat or 0,
            evidence=RealityEvidence.from_mapping(evidence),
        )
        if item["walking_minutes"] is not None:
            assert item["walking_evidence"]["source_reference"] == TransitDurationService.walking_endpoint
            assert item["walking_evidence"]["observed_at"]
            assert item["walking_admission"]["authority"] == (
                "PLACE_CONTEXT_WALKING_TIME_ADMISSION"
            )
    assert stored.place_context[0]["anchor_candidate"] is True
    assert {link["external_id"] for link in stored.place_context[0]["co_located_with"]} >= {"mall-2", "station"}
    assert stored.place_context[0]["walking_minutes"] == 5
    assert not any(item["category"] == "HEALTHCARE" for item in stored.place_context)
    assert stored.rent is None

    # Existing grocery fields have no observation evidence and are not silently
    # promoted into this acquisition's admitted Reality list.
    assert all(item["external_id"] != "grocery" for item in stored.place_context)
    reread = client.get(
        f"/api/properties?conversation_id={conversation_id}",
    )
    assert reread.status_code == 200
    api_property = next(
        item for item in reread.json()["items"] if item["id"] == home.id
    )
    assert api_property["place_context"] == stored.place_context
    assert all(item["admission"]["status"] == "ADMITTED"
               for item in api_property["place_context"])


def test_nearby_reality_admission_rejects_incomplete_identity_and_future_time():
    home = Property(
        id="property-1",
        geographic_identity="grounded home",
        geographic_status=GeographicStatus.GROUNDED,
        lng=104.074,
        lat=30.668,
    )
    incomplete = PlacePoi(
        external_id="poi-1", name="mall", identity="", type_code="060101",
        lng=104.075, lat=30.669, distance_m=100,
        observed_at="2026-09-01T00:00:00+00:00",
    )
    assert not is_admitted_nearby_reality(incomplete, home)
    assert PlaceContextRealityService.admit(
        home=home,
        category="COMMERCIAL",
        place=incomplete,
        walking_minutes=5,
        walking_evidence=None,
        anchor_candidate=True,
    ) is None

    future = PlacePoi(
        external_id="poi-1", name="mall", identity="district mall",
        type_code="060101", lng=104.075, lat=30.669, distance_m=100,
        observed_at="2099-01-01T00:00:00+00:00",
    )
    assert PlaceContextRealityService.admit(
        home=home,
        category="COMMERCIAL",
        place=future,
        walking_minutes=5,
        walking_evidence=None,
        anchor_candidate=True,
    ) is None


# Captured from the real bounded Chengdu Provider trace; no synthetic station.
TRAM_PROVIDER_CANDIDATE = {
    "id": "BV11115831", "name": "天欣路站(有轨电车站)",
    "type": "交通设施服务;公交车站;电车站", "typecode": "150705",
    "cityname": "成都市", "adname": "郫都区", "address": "有轨电车蓉2号线",
    "location": "103.921684,30.756920", "distance": "360",
}
OBSERVED_AT = "2026-10-23T21:33:33.055660+00:00"


def test_real_tram_candidate_uses_existing_evidence_and_admission_binding():
    place = _parse_place(TRAM_PROVIDER_CANDIDATE,
                         PlaceContextRealityService.category_types["TRANSIT"], OBSERVED_AT)
    assert place is not None
    assert (place.external_id, place.type_code, place.lng, place.lat) == (
        "BV11115831", "150705", 103.921684, 30.756920,
    )
    home = Property(id="home", geographic_identity="四川省成都市郫都区龙湖·时代天街",
                    geographic_status=GeographicStatus.GROUNDED, lng=103.920730, lat=30.753792)
    admitted = PlaceContextRealityService.admit(
        home=home, category="TRANSIT", place=place,
        walking_minutes=None, walking_evidence=None, anchor_candidate=False,
    )
    assert is_admitted_nearby_reality(admitted, home)
    assert admitted["evidence"]["source_record_id"] == place.external_id
    assert admitted["evidence"]["source_reference"] == PlaceContextRealityService.endpoint
    assert admitted["admission"]["authority"] == "PLACE_CONTEXT_REALITY_ADMISSION"
    assert not is_admitted_nearby_reality(admitted, replace(home, id="another-home"))
    assert not is_admitted_nearby_reality({**admitted, "evidence": None}, home)
    assert PlaceContextRealityService.admit(
        home=home, category="TRANSIT", place=replace(place, external_id=""),
        walking_minutes=None, walking_evidence=None, anchor_candidate=False,
    ) is None


def test_existing_metro_type_is_still_accepted():
    metro = {"id": "BV10738798", "name": "红高路(地铁站)", "typecode": "150500",
             "cityname": "成都市", "adname": "郫都区", "address": "6号线",
             "location": "103.937108,30.769421", "distance": "2341"}
    assert _parse_place(metro, PlaceContextRealityService.category_types["TRANSIT"],
                        OBSERVED_AT).type_code == "150500"


@pytest.mark.parametrize("type_code", ["150501", "150000", "150701", "150800", "060101"])
def test_parent_query_does_not_admit_unrelated_or_unapproved_children(type_code):
    assert _parse_place({**TRAM_PROVIDER_CANDIDATE, "typecode": type_code},
                        PlaceContextRealityService.category_types["TRANSIT"], OBSERVED_AT) is None


def test_transit_preserves_multiple_stations_per_mode_and_refreshes_legacy_cache_once(monkeypatch):
    cid = uuid_for("bounded-transit-preservation")
    create_owned_conversation(TestClient(app), cid)
    home = property_manager.create(cid, Property(
        title="已确认住所", geographic_identity="已确认住所身份",
        geographic_status=GeographicStatus.GROUNDED, lng=103.92073, lat=30.753792,
    ))

    def place(identifier, code, distance):
        return PlacePoi(identifier, identifier, f"真实区域 {identifier}", code,
                        103.921684, 30.75692, distance, OBSERVED_AT)

    transit = [place(f"bus-{i}", "150700", 100 + i) for i in range(3)] + [
        place(f"tram-{i}", "150705", 300 + i) for i in range(3)
    ] + [place(f"metro-{i}", "150500", 500 + i) for i in range(3)]
    legacy = [PlaceContextRealityService.admit(
        home=home, category="TRANSIT", place=item, walking_minutes=None,
        walking_evidence=None, anchor_candidate=False,
    ) for item in transit[:2]]
    property_manager.update_place_context(home.id, cid, legacy)
    discoveries = []

    def discover(_lng, _lat, types, _key):
        discoveries.append(types)
        if types == PlaceContextRealityService.category_types["TRANSIT"]:
            return [*transit, transit[0]]  # Provider duplicate is retained only once.
        if types == PlaceContextRealityService.category_types["COMMERCIAL"]:
            return [place(f"mall-{i}", "060101", 50 + i) for i in range(3)]
        return []

    class Walking:
        def calculate_walking_minutes(self, **kwargs):
            return None  # Missing route evidence must not become an invented duration.

    service = PlaceContextRealityService(transit=Walking())
    monkeypatch.setattr(service, "_discover", discover)
    result = service.establish(cid, home.id, "test-key")
    assert result.status == "UPDATED"
    stored = property_manager.get_scoped(home.id, cid)
    retained = [item for item in stored.place_context if item["category"] == "TRANSIT"]
    assert [item["external_id"] for item in retained] == [item.external_id for item in transit]
    assert all(is_admitted_nearby_reality(item, stored) for item in retained)
    assert all(item["walking_minutes"] is None for item in retained)
    assert len([item for item in stored.place_context if item["category"] == "COMMERCIAL"]) == 2
    calls = len(discoveries)
    assert service.establish(cid, home.id, "test-key").status == "EXISTING"
    assert len(discoveries) == calls


def test_empty_transit_refresh_preserves_existing_admitted_evidence(monkeypatch):
    cid = uuid_for("transit-refresh-no-evidence")
    create_owned_conversation(TestClient(app), cid)
    home = property_manager.create(cid, Property(
        title="已确认住所", geographic_identity="已确认住所身份",
        geographic_status=GeographicStatus.GROUNDED, lng=103.92073, lat=30.753792,
    ))
    tram = _parse_place(TRAM_PROVIDER_CANDIDATE,
                        PlaceContextRealityService.category_types["TRANSIT"], OBSERVED_AT)
    old = [PlaceContextRealityService.admit(
        home=home, category="TRANSIT", place=tram, walking_minutes=None,
        walking_evidence=None, anchor_candidate=False,
    )]
    property_manager.update_place_context(home.id, cid, old)
    service = PlaceContextRealityService()
    monkeypatch.setattr(service, "_discover", lambda *args: [])
    assert service.establish(cid, home.id, "test-key").status == "NO_RELIABLE_REALITY"
    assert property_manager.get_scoped(home.id, cid).place_context == old
