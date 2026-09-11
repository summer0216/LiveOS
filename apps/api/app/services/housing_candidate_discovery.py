from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.models.property import (
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
)
from app.services.property_manager import PropertyManager, property_manager
from app.services.transit_duration import (
    LivingTimeResult,
    TransitDurationService,
    transit_duration_service,
)


@dataclass(frozen=True)
class ResidentialPoi:
    poi_id: str
    name: str
    address: str | None
    city: str | None
    city_code: str | None
    lng: float
    lat: float
    poi_type: str


@dataclass(frozen=True)
class HousingDiscoveryResult:
    raw_poi_count: int
    residential_poi_count: int
    commute_qualified_count: int
    properties: tuple[Property, ...]


class HousingCandidateDiscovery:
    endpoint = "https://restapi.amap.com/v3/place/around"
    residential_type = "120302"

    def __init__(
        self,
        *,
        properties: PropertyManager = property_manager,
        transit: TransitDurationService = transit_duration_service,
    ) -> None:
        self._properties = properties
        self._transit = transit

    def discover(
        self,
        *,
        conversation_id: str,
        work_lng: float,
        work_lat: float,
        commute_limit_minutes: int,
        api_key: str | None,
        radius_meters: int = 8_000,
        pages: int = 2,
        page_size: int = 20,
        max_route_candidates: int = 16,
        max_results: int = 4,
    ) -> HousingDiscoveryResult:
        if not api_key or commute_limit_minutes < 1:
            return HousingDiscoveryResult(0, 0, 0, ())

        raw: list[dict] = []
        for page in range(1, pages + 1):
            try:
                response = httpx.get(
                    self.endpoint,
                    params={
                        "key": api_key,
                        "location": f"{work_lng:.6f},{work_lat:.6f}",
                        "radius": radius_meters,
                        "types": self.residential_type,
                        "sortrule": "distance",
                        "offset": page_size,
                        "page": page,
                        "extensions": "all",
                    },
                    timeout=10,
                )
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, TypeError, ValueError):
                continue
            if payload.get("status") != "1":
                continue
            page_items = payload.get("pois") or []
            raw.extend(item for item in page_items if isinstance(item, dict))
            if len(page_items) < page_size:
                break

        residential = self._validated_residential_pois(raw)
        qualified: list[tuple[LivingTimeResult, ResidentialPoi]] = []
        for poi in residential[:max_route_candidates]:
            living_time = self._transit.calculate_living_time(
                origin_lng=poi.lng,
                origin_lat=poi.lat,
                destination_lng=work_lng,
                destination_lat=work_lat,
                api_key=api_key,
                origin_city_code=poi.city_code,
                destination_city_code=poi.city_code,
            )
            if (
                living_time is not None
                and living_time.minutes <= commute_limit_minutes
            ):
                qualified.append((living_time, poi))

        qualified.sort(
            key=lambda item: (item[0].minutes, item[1].name, item[1].poi_id)
        )
        existing = {
            item.external_id: item
            for item in self._properties.list(conversation_id)
            if item.conversation_id == conversation_id
            and item.provenance == PropertyProvenance.AMAP_RESIDENTIAL_POI
            and item.external_id
        }
        persisted: list[Property] = []
        for living_time, poi in qualified[:max_results]:
            property_ = existing.get(poi.poi_id)
            if property_ is None:
                property_ = self._properties.create(
                    conversation_id,
                    Property(
                        title=poi.name,
                        district=poi.city,
                        rent=None,
                        commute_minutes=living_time.minutes,
                        commute_mode=living_time.mode,
                        geographic_identity=_geographic_identity(poi),
                        geographic_precision=GeographicPrecision.COMMUNITY,
                        geographic_status=GeographicStatus.GROUNDED,
                        lng=poi.lng,
                        lat=poi.lat,
                        provenance=PropertyProvenance.AMAP_RESIDENTIAL_POI,
                        external_id=poi.poi_id,
                    ),
                )
            else:
                updated = self._properties.update_commute_minutes(
                    property_.id or "",
                    conversation_id,
                    living_time.minutes,
                    living_time.mode,
                )
                property_ = updated or property_
            persisted.append(property_)

        return HousingDiscoveryResult(
            raw_poi_count=len(raw),
            residential_poi_count=len(residential),
            commute_qualified_count=len(qualified),
            properties=tuple(persisted),
        )

    @staticmethod
    def _validated_residential_pois(raw: list[dict]) -> list[ResidentialPoi]:
        by_identity: dict[str, ResidentialPoi] = {}
        coordinate_keys: set[tuple[float, float]] = set()
        for item in raw:
            poi = _parse_residential_poi(item)
            if poi is None or poi.poi_id in by_identity:
                continue
            coordinate_key = (round(poi.lng, 6), round(poi.lat, 6))
            if coordinate_key in coordinate_keys:
                continue
            by_identity[poi.poi_id] = poi
            coordinate_keys.add(coordinate_key)
        return list(by_identity.values())


def _parse_residential_poi(item: dict) -> ResidentialPoi | None:
    poi_type = str(item.get("type") or "")
    type_code = str(item.get("typecode") or "")
    if "商务住宅;住宅区;住宅小区" not in poi_type or type_code != "120302":
        return None
    if any(token in poi_type for token in ("内部设施", "附属设施")):
        return None
    poi_id = str(item.get("id") or "").strip()
    name = str(item.get("name") or "").strip()
    location = str(item.get("location") or "").split(",")
    city_code = item.get("citycode")
    if (
        not poi_id
        or not name
        or len(location) != 2
        or not isinstance(city_code, str)
        or not city_code.strip()
    ):
        return None
    try:
        lng, lat = (float(value) for value in location)
    except ValueError:
        return None
    if not (-180 <= lng <= 180 and -90 <= lat <= 90):
        return None
    address = item.get("address")
    city = item.get("cityname")
    return ResidentialPoi(
        poi_id=poi_id,
        name=name,
        address=address.strip() if isinstance(address, str) and address.strip() else None,
        city=city.strip() if isinstance(city, str) and city.strip() else None,
        city_code=city_code.strip(),
        lng=lng,
        lat=lat,
        poi_type=poi_type,
    )


def _geographic_identity(poi: ResidentialPoi) -> str:
    return "".join(part for part in (poi.city, poi.address, poi.name) if part)


housing_candidate_discovery = HousingCandidateDiscovery()
