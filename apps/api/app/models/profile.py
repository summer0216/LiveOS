from dataclasses import dataclass, field

from app.models.profile_patch import PROFILE_FIELDS, LivingProfilePatch

PREFERENCE_TAG_CATEGORIES = (
    "preference",
    "commute",
    "lifestyle",
    "budget",
)


def create_empty_preference_tags() -> dict[str, list[str]]:
    return {category: [] for category in PREFERENCE_TAG_CATEGORIES}


@dataclass
class LivingProfile:
    work_location: str | None = None
    budget: int | None = None
    commute_minutes: int | None = None
    preferred_city: str | None = None
    family_size: int | None = None
    has_pet: bool | None = None
    latest_insights: list[str] = field(default_factory=list)
    preference_tags: dict[str, list[str]] = field(
        default_factory=create_empty_preference_tags,
    )

    def apply_patch(
        self,
        patch: LivingProfilePatch,
    ) -> None:
        for field_name in PROFILE_FIELDS:
            if field_name in patch.clear_fields:
                setattr(self, field_name, None)
                continue

            value = getattr(patch, field_name)
            if value is not None:
                setattr(self, field_name, value)
