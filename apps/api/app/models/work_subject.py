from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class WorkSubject:
    identity: str
    geographic_identity: str
    geographic_precision: Literal["PLACE"]
    geographic_status: Literal["GROUNDED"]
    lng: float
    lat: float
    relationship: Literal["WORK"] = "WORK"
