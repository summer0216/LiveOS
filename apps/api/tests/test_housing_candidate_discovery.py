from dataclasses import replace

from app.models.property import CommuteMode, Property, PropertyProvenance
from app.services.housing_candidate_discovery import HousingCandidateDiscovery
from app.services.transit_duration import LivingTimeResult


class Response:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeProperties:
    def __init__(self) -> None:
        self.items: list[Property] = []

    def list(self, _conversation_id: str) -> list[Property]:
        return self.items.copy()

    def create(self, conversation_id: str, property_: Property) -> Property:
        stored = replace(
            property_, id=f"property-{len(self.items) + 1}", conversation_id=conversation_id
        )
        self.items.append(stored)
        return stored

    def update_commute_minutes(
        self,
        property_id: str,
        _conversation_id: str,
        commute_minutes: int | None,
        commute_mode: CommuteMode | None = None,
    ) -> Property | None:
        for index, property_ in enumerate(self.items):
            if property_.id == property_id:
                updated = replace(
                    property_,
                    commute_minutes=commute_minutes,
                    commute_mode=commute_mode,
                )
                self.items[index] = updated
                return updated
        return None


class FakeTransit:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def calculate_living_time(self, **kwargs) -> LivingTimeResult | None:
        self.calls.append(kwargs)
        minutes = {113.950000: 26, 113.960000: 34}.get(kwargs["origin_lng"])
        return (
            LivingTimeResult(minutes, CommuteMode.WALKING)
            if minutes is not None
            else None
        )


def residential_poi(
    poi_id: str,
    name: str,
    location: str,
    *,
    poi_type: str = "商务住宅;住宅区;住宅小区",
    typecode: str = "120302",
) -> dict:
    return {
        "id": poi_id,
        "name": name,
        "address": "科苑路",
        "cityname": "深圳市",
        "citycode": "0755",
        "location": location,
        "type": poi_type,
        "typecode": typecode,
    }


def test_discovers_only_real_residential_pois_with_viable_home_to_work_commute(
    monkeypatch,
) -> None:
    raw = [
        residential_poi("poi-1", "真实小区一", "113.950000,22.540000"),
        residential_poi("poi-1", "真实小区一", "113.950000,22.540000"),
        residential_poi("poi-2", "真实小区二", "113.960000,22.550000"),
        residential_poi(
            "poi-3",
            "园区停车场",
            "113.970000,22.560000",
            poi_type="交通设施服务;停车场;公共停车场",
            typecode="150904",
        ),
    ]
    monkeypatch.setattr(
        "httpx.get",
        lambda *_args, **_kwargs: Response({"status": "1", "pois": raw}),
    )
    properties = FakeProperties()
    transit = FakeTransit()
    discovery = HousingCandidateDiscovery(properties=properties, transit=transit)

    result = discovery.discover(
        conversation_id="conversation-1",
        work_lng=113.947,
        work_lat=22.541,
        commute_limit_minutes=30,
        api_key="test-key",
        pages=1,
    )

    assert result.raw_poi_count == 4
    assert result.residential_poi_count == 2
    assert result.commute_qualified_count == 1
    assert len(result.properties) == 1
    candidate = result.properties[0]
    assert candidate.title == "真实小区一"
    assert candidate.rent is None
    assert candidate.commute_minutes == 26
    assert candidate.commute_mode == CommuteMode.WALKING
    assert candidate.provenance == PropertyProvenance.AMAP_RESIDENTIAL_POI
    assert candidate.external_id == "poi-1"
    assert transit.calls[0]["origin_lng"] == 113.95
    assert transit.calls[0]["destination_lng"] == 113.947


def test_discovery_is_idempotent_by_amap_poi_identity(monkeypatch) -> None:
    raw = [residential_poi("poi-1", "真实小区一", "113.950000,22.540000")]
    monkeypatch.setattr(
        "httpx.get",
        lambda *_args, **_kwargs: Response({"status": "1", "pois": raw}),
    )
    properties = FakeProperties()
    discovery = HousingCandidateDiscovery(
        properties=properties,
        transit=FakeTransit(),
    )
    parameters = {
        "conversation_id": "conversation-1",
        "work_lng": 113.947,
        "work_lat": 22.541,
        "commute_limit_minutes": 30,
        "api_key": "test-key",
        "pages": 1,
    }

    first = discovery.discover(**parameters)
    second = discovery.discover(**parameters)

    assert first.properties[0].id == second.properties[0].id
    assert len(properties.items) == 1
