from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.models.property import GeographicStatus, Property
from app.services.property_manager import PropertyManager, property_manager
from app.services.transit_duration import (
    TransitDurationService,
    transit_duration_service,
)


@dataclass(frozen=True)
class GroceryRealityResult:
    status: str
    property: Property | None = None


@dataclass(frozen=True)
class GroceryPoi:
    poi_id: str
    name: str
    identity: str
    lng: float
    lat: float
    distance: int


class DailyGroceryRealityService:
    endpoint = "https://restapi.amap.com/v3/place/around"
    grocery_type = "060400"

    def __init__(
        self,
        *,
        properties: PropertyManager = property_manager,
        transit: TransitDurationService = transit_duration_service,
    ) -> None:
        self._properties = properties
        self._transit = transit

    def establish(
        self,
        conversation_id: str,
        property_id: str,
        api_key: str | None,
    ) -> GroceryRealityResult:
        home = self._properties.get_scoped(property_id, conversation_id)
        if (
            home is None
            or home.geographic_status != GeographicStatus.GROUNDED
            or home.lng is None
            or home.lat is None
            or not api_key
        ):
            return GroceryRealityResult("NOT_FOUND")
        if (
            home.grocery_external_id
            and home.grocery_lng is not None
            and home.grocery_lat is not None
            and home.grocery_walking_minutes is not None
        ):
            return GroceryRealityResult("EXISTING", home)

        for grocery in self._discover(home.lng, home.lat, api_key):
            minutes = self._transit.calculate_walking_minutes(
                origin_lng=home.lng,
                origin_lat=home.lat,
                destination_lng=grocery.lng,
                destination_lat=grocery.lat,
                api_key=api_key,
            )
            if minutes is None:
                continue
            updated = self._properties.update_daily_grocery(
                property_id,
                conversation_id,
                external_id=grocery.poi_id,
                name=grocery.name,
                identity=grocery.identity,
                lng=grocery.lng,
                lat=grocery.lat,
                walking_minutes=minutes,
            )
            return GroceryRealityResult("UPDATED" if updated else "NOT_FOUND", updated)
        return GroceryRealityResult("NO_RELIABLE_REALITY")

    def _discover(self, lng: float, lat: float, api_key: str) -> list[GroceryPoi]:
        try:
            response = httpx.get(
                self.endpoint,
                params={
                    "key": api_key,
                    "location": f"{lng:.6f},{lat:.6f}",
                    "radius": 2_000,
                    "types": self.grocery_type,
                    "sortrule": "distance",
                    "offset": 10,
                    "page": 1,
                    "extensions": "all",
                },
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, TypeError, ValueError):
            return []
        if payload.get("status") != "1":
            return []
        candidates = [
            poi
            for item in payload.get("pois") or []
            if isinstance(item, dict) and (poi := _parse_grocery(item)) is not None
        ]
        return sorted(candidates, key=lambda item: (item.distance, item.name, item.poi_id))


def _parse_grocery(item: dict) -> GroceryPoi | None:
    poi_id = str(item.get("id") or "").strip()
    name = str(item.get("name") or "").strip()
    type_code = str(item.get("typecode") or "").strip()
    poi_type = str(item.get("type") or "")
    location = str(item.get("location") or "").split(",")
    if (
        not poi_id
        or not name
        or type_code != DailyGroceryRealityService.grocery_type
        or "超级市场" not in poi_type
        or len(location) != 2
    ):
        return None
    try:
        lng, lat = (float(value) for value in location)
        distance = int(float(item.get("distance")))
    except (TypeError, ValueError):
        return None
    if not (-180 <= lng <= 180 and -90 <= lat <= 90) or distance < 0:
        return None
    address = item.get("address")
    identity = " ".join(
        part for part in (
            item.get("cityname"),
            item.get("adname"),
            address if isinstance(address, str) else None,
            name,
        ) if isinstance(part, str) and part.strip()
    )
    return GroceryPoi(poi_id, name, identity, lng, lat, distance)


daily_grocery_reality_service = DailyGroceryRealityService()
