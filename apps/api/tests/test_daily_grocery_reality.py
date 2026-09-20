from fastapi.testclient import TestClient

from app.main import app
from app.models.property import (
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
)
from app.services.daily_grocery_reality import DailyGroceryRealityService
from app.services.property_manager import property_manager
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


class FakeResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {
            "status": "1",
            "pois": [{
                "id": "amap-grocery-1",
                "name": "真实生活超市",
                "type": "购物服务;超级市场;超市",
                "typecode": "060400",
                "location": "116.321000,39.984000",
                "distance": "420",
                "cityname": "北京市",
                "adname": "海淀区",
                "address": "中关村大街1号",
            }],
        }


class FakeWalking:
    def calculate_walking_minutes(self, **kwargs) -> int:
        assert kwargs["origin_lng"] == 116.320000
        assert kwargs["destination_lng"] == 116.321000
        return 6


def test_grounded_home_persists_real_grocery_walking_relationship(monkeypatch):
    client = TestClient(app)
    conversation_id = uuid_for("daily-grocery-reality")
    create_owned_conversation(client, conversation_id)
    home = property_manager.create(conversation_id, Property(
        title="中关村东大院",
        geographic_identity="北京市海淀区中关村东大院",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.320000,
        lat=39.985000,
        provenance=PropertyProvenance.AMAP_RESIDENTIAL_POI,
        external_id="amap-home-1",
    ))
    monkeypatch.setattr(
        "app.services.daily_grocery_reality.httpx.get",
        lambda *args, **kwargs: FakeResponse(),
    )
    service = DailyGroceryRealityService(transit=FakeWalking())

    result = service.establish(
        conversation_id,
        home.id or "",
        "test-amap-key",
    )

    assert result.status == "UPDATED"
    stored = property_manager.get_scoped(home.id or "", conversation_id)
    assert stored is not None
    assert stored.grocery_external_id == "amap-grocery-1"
    assert stored.grocery_name == "真实生活超市"
    assert stored.grocery_identity == "北京市 海淀区 中关村大街1号 真实生活超市"
    assert (stored.grocery_lng, stored.grocery_lat) == (116.321, 39.984)
    assert stored.grocery_walking_minutes == 6
