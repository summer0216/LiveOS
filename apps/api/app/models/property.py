from dataclasses import dataclass
from enum import Enum


class GeographicPrecision(str, Enum):
    PLACE = "PLACE"
    COMMUNITY = "COMMUNITY"
    STREET = "STREET"
    AREA = "AREA"


class GeographicStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    GROUNDED = "GROUNDED"


class PropertyProvenance(str, Enum):
    USER_PROVIDED = "USER_PROVIDED"
    AMAP_RESIDENTIAL_POI = "AMAP_RESIDENTIAL_POI"


class PropertyRentSource(str, Enum):
    USER_CONFIRMED_REALITY = "USER_CONFIRMED_REALITY"


class CommuteMode(str, Enum):
    WALKING = "WALKING"
    PUBLIC_TRANSIT = "PUBLIC_TRANSIT"


@dataclass
class Property:
    id: str | None = None
    conversation_id: str | None = None
    title: str | None = None
    district: str | None = None
    rent: int | None = None
    rent_source: PropertyRentSource | None = None
    area: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    commute_minutes: int | None = None
    commute_mode: CommuteMode | None = None
    pet_friendly: bool | None = None
    geographic_identity: str | None = None
    geographic_precision: GeographicPrecision | None = None
    geographic_status: GeographicStatus = GeographicStatus.UNRESOLVED
    lng: float | None = None
    lat: float | None = None
    provenance: PropertyProvenance = PropertyProvenance.USER_PROVIDED
    external_id: str | None = None
