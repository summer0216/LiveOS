from fastapi.testclient import TestClient

from app.main import app
from app.models.property import (
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
)
from app.services.place_context_reality import PlaceContextRealityService
from app.services.property_manager import property_manager
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
        if types == "150500|150700":
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
        ("GROCERY", "grocery"), ("COMMERCIAL", "mall"),
        ("COMMERCIAL", "mall-2"), ("TRANSIT", "station"),
        ("EDUCATION", "university"),
    ]
    assert len(stored.place_context) <= 9
    assert all(item["structure_version"] == 2 for item in stored.place_context)
    assert all(item["name"] and item["identity"] and item["lng"] and item["lat"] for item in stored.place_context)
    assert stored.place_context[1]["anchor_candidate"] is True
    assert stored.place_context[0]["anchor_candidate"] is False
    assert {link["external_id"] for link in stored.place_context[0]["co_located_with"]} >= {"mall", "station"}
    assert stored.place_context[1]["walking_minutes"] == 5
    assert not any(item["category"] == "HEALTHCARE" for item in stored.place_context)
    assert stored.rent is None
