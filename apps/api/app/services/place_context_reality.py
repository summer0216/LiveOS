from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
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
        "HEALTHCARE": ("090101", "090102"),
    }
    anchor_types: ClassVar[frozenset[str]] = frozenset({
        "060101", "150500", "141201", "090101",
    })
    max_per_category = 2
    co_location_radius_m = 1_000

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
        if home.place_context and all(
            item.get("structure_version") == 2 for item in home.place_context
        ):
            return PlaceContextResult("EXISTING", home)

        items: list[dict] = []
        if (
            home.grocery_external_id and home.grocery_name
            and home.grocery_identity
            and home.grocery_lng is not None and home.grocery_lat is not None
        ):
            items.append({
                "structure_version": 2,
                "category": "GROCERY",
                "external_id": home.grocery_external_id,
                "name": home.grocery_name,
                "identity": home.grocery_identity,
                "type_code": "060400",
                "lng": home.grocery_lng,
                "lat": home.grocery_lat,
                "distance_m": round(_distance_m(
                    home.lng, home.lat, home.grocery_lng, home.grocery_lat,
                )),
                "walking_minutes": home.grocery_walking_minutes,
                "anchor_candidate": False,
            })
        for category, allowed_types in self.category_types.items():
            candidates = self._discover(home.lng, home.lat, allowed_types, api_key)
            seen: set[str] = set()
            # Type identifies the facility kind; distance orders facts, not value.
            for selected in sorted(candidates, key=lambda poi: (poi.distance_m, poi.external_id)):
                if selected.external_id in seen:
                    continue
                seen.add(selected.external_id)
                minutes = self._transit.calculate_walking_minutes(
                    origin_lng=home.lng,
                    origin_lat=home.lat,
                    destination_lng=selected.lng,
                    destination_lat=selected.lat,
                    api_key=api_key,
                )
                items.append({
                    "structure_version": 2,
                    "category": category,
                    "external_id": selected.external_id,
                    "name": selected.name,
                    "identity": selected.identity,
                    "type_code": selected.type_code,
                    "lng": selected.lng,
                    "lat": selected.lat,
                    "distance_m": selected.distance_m,
                    "walking_minutes": minutes,
                    "anchor_candidate": selected.type_code in self.anchor_types,
                })
                if len(seen) >= self.max_per_category:
                    break

        anchors = [item for item in items if item["anchor_candidate"]]
        for item in items:
            item["co_located_with"] = [
                {"external_id": anchor["external_id"], "distance_m": round(distance)}
                for anchor in anchors
                if anchor["external_id"] != item["external_id"]
                and (distance := _distance_m(
                    item["lng"], item["lat"], anchor["lng"], anchor["lat"],
                )) <= self.co_location_radius_m
            ]

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


def _distance_m(lng_a: float, lat_a: float, lng_b: float, lat_b: float) -> float:
    latitude_delta = radians(lat_b - lat_a)
    longitude_delta = radians(lng_b - lng_a)
    arc = sin(latitude_delta / 2) ** 2 + (
        cos(radians(lat_a)) * cos(radians(lat_b)) * sin(longitude_delta / 2) ** 2
    )
    return 12_742_000 * asin(min(1, sqrt(arc)))


place_context_reality_service = PlaceContextRealityService()
