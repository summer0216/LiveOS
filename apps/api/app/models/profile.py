from dataclasses import dataclass

from app.models.profile_patch import LivingProfilePatch


@dataclass
class LivingProfile:
    work_location: str | None = None
    budget: int | None = None
    commute_minutes: int | None = None
    preferred_city: str | None = None
    family_size: int | None = None
    has_pet: bool | None = None

    def apply_patch(
        self,
        patch: LivingProfilePatch,
    ) -> None:

        if patch.work_location is not None:
            self.work_location = patch.work_location

        if patch.budget is not None:
            self.budget = patch.budget

        if patch.commute_minutes is not None:
            self.commute_minutes = patch.commute_minutes

        if patch.preferred_city is not None:
            self.preferred_city = patch.preferred_city

        if patch.family_size is not None:
            self.family_size = patch.family_size

        if patch.has_pet is not None:
            self.has_pet = patch.has_pet
