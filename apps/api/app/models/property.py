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
    USER_PROVIDED = "USER_PROVIDED"
    USER_CONFIRMED_REALITY = "USER_CONFIRMED_REALITY"
    EXTERNAL_SOURCE = "EXTERNAL_SOURCE"


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
    rent_source_reference: str | None = None
    rent_observed_at: str | None = None
    independent_kitchen: bool | None = None
    independent_kitchen_source: str | None = None
    indoor_sound_observation: str | None = None
    indoor_sound_observation_source: str | None = None
    indoor_sound_observation_unknown: str | None = None
    grocery_external_id: str | None = None
    grocery_name: str | None = None
    grocery_identity: str | None = None
    grocery_lng: float | None = None
    grocery_lat: float | None = None
    grocery_walking_minutes: int | None = None
    living_meaning: str | None = None
    living_meaning_reality_hash: str | None = None
    current_judgment: str | None = None
    current_judgment_state_hash: str | None = None
    meaningful_unknown: str | None = None
    meaningful_unknown_why: str | None = None
    meaningful_unknown_state_hash: str | None = None
    reality_action_type: str | None = None
    reality_action_label: str | None = None
    reality_action_why: str | None = None
    reality_action_state_hash: str | None = None
    public_rent_evidence: dict | None = None
    public_action_outcome: str | None = None
    feedback_move_type: str | None = None
    feedback_move_label: str | None = None
    feedback_move_why: str | None = None
    feedback_state_hash: str | None = None
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
