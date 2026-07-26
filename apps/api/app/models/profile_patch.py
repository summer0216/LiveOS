from dataclasses import dataclass


@dataclass
class LivingProfilePatch:
    work_location: str | None = None
    budget: int | None = None
    commute_minutes: int | None = None
    preferred_city: str | None = None
    family_size: int | None = None
    has_pet: bool | None = None
