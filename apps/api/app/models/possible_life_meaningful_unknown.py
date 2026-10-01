from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PossibleLifeMeaningfulUnknown:
    id: str
    possible_life_id: str
    personal_meaning_id: str
    question: str
    why_it_matters: str
    state_hash: str
    resolved_at: datetime | None = None
    resolved_property_id: str | None = None
    resolved_layout_expression: str | None = None
    resolved_reality_source: str | None = None
