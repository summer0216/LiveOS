from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import httpx
from app.models.property import GeographicStatus, Property
from app.services.property_manager import PropertyManager, property_manager
from app.services.transit_duration import (
    TransitDurationService,
    transit_duration_service,
)


@dataclass(frozen=True)
class PlaceContextResult:
    status: str
    property: Property | None = None


@dataclass(frozen=True)
class PlacePoi:
    external_id: str
    name: str
    identity: str
    type_code: str
    lng: float
    lat: float
    distance_m: int


class PlaceContextRealityService:
    endpoint = "https://restapi.amap.com/v3/place/around"
    category_types: ClassVar[dict[str, tuple[str, ...]]] = {
        "COMMERCIAL": ("060101",),  # Shopping centre, not an individual shop.
        "TRANSIT": ("150500", "150700"),  # Station before bus stop.
        "EDUCATION": ("141201", "141202", "141203"),
    }

    def __init__(
        self,
        *,
        properties: PropertyManager = property_manager,
        transit: TransitDurationService = transit_duration_service,
    ) -> None:
        self._properties = properties
        self._transit = transit

    def establish(
        self, conversation_id: str, property_id: str, api_key: str | None,
    ) -> PlaceContextResult:
        home = self._properties.get_scoped(property_id, conversation_id)
        if (
            home is None
            or home.geographic_status != GeographicStatus.GROUNDED
            or home.lng is None
            or home.lat is None
            or not api_key
        ):
            return PlaceContextResult("NOT_FOUND")
        if home.place_context is not None:
            return PlaceContextResult("EXISTING", home)

        items: list[dict] = []
        for category, allowed_types in self.category_types.items():
            candidates = self._discover(home.lng, home.lat, allowed_types, api_key)
            if not candidates:
                continue
            # Provider category specificity is evidence of facility kind; the
            # closest result only breaks ties within that bounded kind.
            selected = min(
                candidates,
                key=lambda poi: (
                    allowed_types.index(poi.type_code), poi.distance_m,
                    poi.external_id,
                ),
            )
            minutes = self._transit.calculate_walking_minutes(
                origin_lng=home.lng,
                origin_lat=home.lat,
                destination_lng=selected.lng,
                destination_lat=selected.lat,
                api_key=api_key,
            )
            items.append({
                "category": category,
                "external_id": selected.external_id,
                "name": selected.name,
                "identity": selected.identity,
                "type_code": selected.type_code,
                "lng": selected.lng,
                "lat": selected.lat,
                "distance_m": selected.distance_m,
                "walking_minutes": minutes,
            })

        updated = self._properties.update_place_context(
            property_id, conversation_id, items,
        )
        return PlaceContextResult("UPDATED" if updated else "NOT_FOUND", updated)

    def _discover(
        self, lng: float, lat: float, allowed_types: tuple[str, ...],
        api_key: str,
    ) -> list[PlacePoi]:
        try:
            response = httpx.get(
                self.endpoint,
                params={
                    "key": api_key,
                    "location": f"{lng:.6f},{lat:.6f}",
                    "radius": 2_000,
                    "types": "|".join(allowed_types),
                    "sortrule": "distance",
                    "offset": 20,
                    "page": 1,
                    "extensions": "all",
                },
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, TypeError, ValueError):
            return []
        if not isinstance(payload, dict) or payload.get("status") != "1":
            return []
        return [
            poi for item in payload.get("pois") or []
            if isinstance(item, dict)
            and (poi := _parse_place(item, allowed_types)) is not None
        ]


def _parse_place(item: dict, allowed_types: tuple[str, ...]) -> PlacePoi | None:
    external_id = str(item.get("id") or "").strip()
    name = str(item.get("name") or "").strip()
    type_code = str(item.get("typecode") or "").strip()
    location = str(item.get("location") or "").split(",")
    if not external_id or not name or type_code not in allowed_types or len(location) != 2:
        return None
    try:
        lng, lat = (float(value) for value in location)
        distance_m = int(float(item.get("distance")))
    except (TypeError, ValueError):
        return None
    if not (-180 <= lng <= 180 and -90 <= lat <= 90) or distance_m < 0:
        return None
    identity = " ".join(
        value for part in (
            item.get("cityname"), item.get("adname"), item.get("address"), name,
        ) if isinstance(part, str) and (value := part.strip())
    )
    return PlacePoi(external_id, name, identity, type_code, lng, lat, distance_m)


place_context_reality_service = PlaceContextRealityService()
