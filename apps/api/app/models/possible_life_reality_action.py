from dataclasses import dataclass
from enum import Enum


class PossibleLifeRealityActionType(str, Enum):
    PUBLIC_EVIDENCE = "PUBLIC_EVIDENCE"
    USER_REALITY = "USER_REALITY"


@dataclass(frozen=True)
class PossibleLifeRealityAction:
    id: str
    possible_life_id: str
    reality_need_id: str
    action_type: PossibleLifeRealityActionType
    label: str
    why: str
    state_hash: str
