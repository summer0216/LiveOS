from dataclasses import dataclass
from typing import Literal

from app.models.property import GeographicPrecision

DecisionGeographyStatus = Literal["UNRESOLVED", "GROUNDED"]
DecisionGeographyIdentitySource = Literal["USER", "INFERRED"]
DecisionGeographyScope = Literal["REGION", "CITY", "LOCAL"]


@dataclass(frozen=True)
class DecisionGeography:
    intent_established: bool = False
    intent_type: str | None = None
    identity: str | None = None
    identity_source: DecisionGeographyIdentitySource | None = None
    geographic_scope: DecisionGeographyScope | None = None
    geographic_identity: str | None = None
    geographic_precision: GeographicPrecision | None = None
    status: DecisionGeographyStatus = "UNRESOLVED"
    lng: float | None = None
    lat: float | None = None
    source_user_turn_id: int | None = None
