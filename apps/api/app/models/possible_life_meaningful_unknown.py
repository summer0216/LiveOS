from dataclasses import dataclass


@dataclass(frozen=True)
class PossibleLifeMeaningfulUnknown:
    id: str
    possible_life_id: str
    personal_meaning_id: str
    question: str
    why_it_matters: str
    state_hash: str
