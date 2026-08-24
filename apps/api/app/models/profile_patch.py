from dataclasses import dataclass, field
from typing import Literal

ProfileField = Literal[
    "work_location",
    "budget",
    "commute_minutes",
    "preferred_city",
    "family_size",
    "has_pet",
]

PROFILE_FIELDS: tuple[ProfileField, ...] = (
    "work_location",
    "budget",
    "commute_minutes",
    "preferred_city",
    "family_size",
    "has_pet",
)


@dataclass
class LivingProfilePatch:
    work_location: str | None = None
    budget: int | None = None
    commute_minutes: int | None = None
    preferred_city: str | None = None
    family_size: int | None = None
    has_pet: bool | None = None
    clear_fields: frozenset[ProfileField] = field(default_factory=frozenset)
