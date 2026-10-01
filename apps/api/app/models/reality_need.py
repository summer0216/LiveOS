from dataclasses import dataclass
from enum import Enum


class RealityNeedResolutionMode(str, Enum):
    ALREADY_KNOWN = "ALREADY_KNOWN"
    USER_ANSWERABLE = "USER_ANSWERABLE"
    REAL_WORLD_CONTACT = "REAL_WORLD_CONTACT"


@dataclass(frozen=True)
class RealityNeed:
    id: str
    possible_life_id: str
    meaningful_unknown_id: str
    needed_reality: str
    resolution_mode: RealityNeedResolutionMode
    known_reality_reference: str | None
    state_hash: str
