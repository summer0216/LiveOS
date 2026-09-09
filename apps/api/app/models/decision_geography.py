from dataclasses import dataclass
from typing import Literal

DecisionGeographyStatus = Literal["UNRESOLVED", "GROUNDED"]
DecisionGeographyIdentitySource = Literal["USER", "INFERRED"]


@dataclass(frozen=True)
class DecisionGeography:
    intent_established: bool = False
    intent_type: str | None = None
    identity: str | None = None
    identity_source: DecisionGeographyIdentitySource | None = None
    status: DecisionGeographyStatus = "UNRESOLVED"
    lng: float | None = None
    lat: float | None = None
