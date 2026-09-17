from dataclasses import dataclass
from typing import Literal

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
    status: DecisionGeographyStatus = "UNRESOLVED"
    lng: float | None = None
    lat: float | None = None
