from dataclasses import dataclass

from app.models.property import CommuteMode


@dataclass(frozen=True)
class PossibleLifePersonalMeaning:
    id: str
    possible_life_id: str
    meaning: str
    living_time_residence_property_id: str
    actual_travel_minutes: int
    actual_travel_mode: CommuteMode
    route_evidence_source: str
    route_evidence_reference: str
    requirement_reference: str
    maximum_commute_minutes: int
    requirement_satisfied: bool
