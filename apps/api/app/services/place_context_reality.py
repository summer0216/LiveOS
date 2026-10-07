from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt
from typing import ClassVar

import httpx
from app.models.property import GeographicStatus, Property
from app.models.reality_evidence import (
    RealityAdmission,
    RealityEvidence,
    is_admitted_reality_record,
)
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
    observed_at: str


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
            is_admitted_nearby_reality(item, home)
            for item in home.place_context
        ):
            return PlaceContextResult("EXISTING", home)

        items: list[dict] = []
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
                walking_evidence = (
                    RealityEvidence(
                        source_provider="AMAP",
                        source_reference=TransitDurationService.walking_endpoint,
                        source_record_id=f"{home.id}:{selected.external_id}:walking",
                        identity=(
                            f"{home.geographic_identity} -> {selected.identity}"
                        ),
                        observed_at=datetime.now(UTC).isoformat(),
                    )
                    if minutes is not None and minutes > 0
                    else None
                )
                admitted = self.admit(
                    home=home,
                    category=category,
                    place=selected,
                    walking_minutes=minutes,
                    walking_evidence=walking_evidence,
                    anchor_candidate=selected.type_code in self.anchor_types,
                )
                if admitted is not None:
                    items.append(admitted)
                if len(seen) >= self.max_per_category:
                    break

        if not items:
            return PlaceContextResult("NO_RELIABLE_REALITY", home)

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

    @staticmethod
    def admit(
        *,
        home: Property,
        category: str,
        place: PlacePoi,
        walking_minutes: int | None,
        walking_evidence: RealityEvidence | None,
        anchor_candidate: bool,
    ) -> dict | None:
        """Admit one provider result only when evidence and Place binding qualify."""
        if (
            not home.id
            or home.geographic_status != GeographicStatus.GROUNDED
            or not home.geographic_identity
            or home.lng is None
            or home.lat is None
            or not place.external_id.strip()
            or not place.name.strip()
            or not place.identity.strip()
            or place.name not in place.identity
            or category not in PlaceContextRealityService.category_types
            or place.type_code
            not in PlaceContextRealityService.category_types.get(category, ())
            or not (-180 <= place.lng <= 180)
            or not (-90 <= place.lat <= 90)
            or place.distance_m < 0
        ):
            return None

        evidence = RealityEvidence(
            source_provider="AMAP",
            source_reference=PlaceContextRealityService.endpoint,
            source_record_id=place.external_id,
            identity=place.identity,
            observed_at=place.observed_at,
        )
        admission = RealityAdmission.admit(
            evidence,
            property_id=home.id,
            property_identity=home.geographic_identity,
            property_lng=home.lng,
            property_lat=home.lat,
            authority="PLACE_CONTEXT_REALITY_ADMISSION",
        )
        if admission is None:
            return None
        walking_admission = None
        if walking_minutes is not None:
            if (
                isinstance(walking_minutes, bool)
                or not isinstance(walking_minutes, int)
                or walking_minutes < 1
                or walking_evidence is None
                or not walking_evidence.qualifies(
                    expected_identity=(
                        f"{home.geographic_identity} -> {place.identity}"
                    ),
                )
                or walking_evidence.source_provider != "AMAP"
                or walking_evidence.source_reference
                != TransitDurationService.walking_endpoint
                or walking_evidence.source_record_id
                != f"{home.id}:{place.external_id}:walking"
            ):
                return None
            walking_admission = RealityAdmission.admit(
                walking_evidence,
                property_id=home.id,
                property_identity=home.geographic_identity,
                property_lng=home.lng,
                property_lat=home.lat,
                authority="PLACE_CONTEXT_WALKING_TIME_ADMISSION",
            )
            if walking_admission is None:
                return None
        elif walking_evidence is not None:
            return None
        return {
            "structure_version": 3,
            "category": category,
            "external_id": place.external_id,
            "name": place.name,
            "identity": place.identity,
            "type_code": place.type_code,
            "lng": place.lng,
            "lat": place.lat,
            "distance_m": place.distance_m,
            "walking_minutes": walking_minutes,
            "anchor_candidate": anchor_candidate,
            "evidence": evidence.to_dict(),
            "admission": admission.to_dict(),
            "walking_evidence": (
                walking_evidence.to_dict() if walking_evidence is not None else None
            ),
            "walking_admission": (
                walking_admission.to_dict() if walking_admission is not None else None
            ),
        }

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
        observed_at = datetime.now(UTC).isoformat()
        return [
            poi for item in payload.get("pois") or []
            if isinstance(item, dict)
            and (poi := _parse_place(item, allowed_types, observed_at)) is not None
        ]


def _parse_place(
    item: dict, allowed_types: tuple[str, ...], observed_at: str,
) -> PlacePoi | None:
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
    if not identity or name not in identity:
        return None
    return PlacePoi(
        external_id, name, identity, type_code, lng, lat, distance_m, observed_at,
    )


def is_admitted_nearby_reality(item: object, home: Property) -> bool:
    if (
        not isinstance(item, dict)
        or item.get("structure_version") != 3
        or not home.id
        or not home.geographic_identity
        or home.lng is None
        or home.lat is None
    ):
        return False
    if not is_admitted_reality_record(
        item,
        property_id=home.id,
        property_identity=home.geographic_identity,
        property_lng=home.lng,
        property_lat=home.lat,
    ):
        return False
    evidence = RealityEvidence.from_mapping(item.get("evidence"))
    admission = RealityAdmission.from_mapping(item.get("admission"))
    name = item.get("name")
    if (
        evidence is None
        or admission is None
        or not isinstance(name, str)
        or not name.strip()
        or name not in evidence.identity
    ):
        return False
    category = item.get("category")
    if not isinstance(category, str):
        return False
    category_types = PlaceContextRealityService.category_types.get(category)
    if (
        evidence.source_provider != "AMAP"
        or evidence.source_reference != PlaceContextRealityService.endpoint
        or not isinstance(category_types, tuple)
        or item.get("type_code") not in category_types
        or not isinstance(item.get("lng"), (int, float))
        or isinstance(item.get("lng"), bool)
        or not isinstance(item.get("lat"), (int, float))
        or isinstance(item.get("lat"), bool)
        or not (-180 <= item["lng"] <= 180)
        or not (-90 <= item["lat"] <= 90)
        or not isinstance(item.get("distance_m"), (int, float))
        or isinstance(item.get("distance_m"), bool)
        or item["distance_m"] < 0
    ):
        return False
    return admission.qualifies_for(
        property_id=home.id,
        property_identity=home.geographic_identity,
        property_lng=home.lng,
        property_lat=home.lat,
        evidence=evidence,
    ) and admission.authority == "PLACE_CONTEXT_REALITY_ADMISSION" and (
        _walking_time_is_admitted(item, home)
    )


def _walking_time_is_admitted(item: dict, home: Property) -> bool:
    minutes = item.get("walking_minutes")
    evidence_value = item.get("walking_evidence")
    admission_value = item.get("walking_admission")
    if minutes is None:
        return evidence_value is None and admission_value is None
    if (
        isinstance(minutes, bool)
        or not isinstance(minutes, int)
        or minutes < 1
        or not home.id
        or not home.geographic_identity
        or home.lng is None
        or home.lat is None
    ):
        return False
    evidence = RealityEvidence.from_mapping(evidence_value)
    admission = RealityAdmission.from_mapping(admission_value)
    if (
        evidence is None
        or admission is None
        or evidence.source_provider != "AMAP"
        or evidence.source_reference != TransitDurationService.walking_endpoint
        or evidence.source_record_id != f"{home.id}:{item.get('external_id')}:walking"
        or evidence.identity != f"{home.geographic_identity} -> {item.get('identity')}"
        or not evidence.qualifies()
    ):
        return False
    return admission.qualifies_for(
        property_id=home.id,
        property_identity=home.geographic_identity,
        property_lng=home.lng,
        property_lat=home.lat,
        evidence=evidence,
    ) and admission.authority == "PLACE_CONTEXT_WALKING_TIME_ADMISSION"


def _distance_m(lng_a: float, lat_a: float, lng_b: float, lat_b: float) -> float:
    latitude_delta = radians(lat_b - lat_a)
    longitude_delta = radians(lng_b - lng_a)
    arc = sin(latitude_delta / 2) ** 2 + (
        cos(radians(lat_a)) * cos(radians(lat_b)) * sin(longitude_delta / 2) ** 2
    )
    return 12_742_000 * asin(min(1, sqrt(arc)))


place_context_reality_service = PlaceContextRealityService()
