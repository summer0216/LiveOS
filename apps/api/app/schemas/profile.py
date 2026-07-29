from pydantic import BaseModel, Field, field_validator

from app.models.profile import (
    PREFERENCE_TAG_CATEGORIES,
    create_empty_preference_tags,
)


class LivingProfileResponse(BaseModel):
    conversation_id: str
    work_location: str | None = None
    budget: int | None = None
    commute_minutes: int | None = None
    preferred_city: str | None = None
    family_size: int | None = None
    has_pet: bool | None = None

    latest_insights: list[str] = Field(default_factory=list)
    preference_tags: dict[str, list[str]] = Field(
        default_factory=create_empty_preference_tags,
    )


class PreferenceTagsUpdateRequest(BaseModel):
    preference_tags: dict[str, list[str]]

    @field_validator("preference_tags")
    @classmethod
    def validate_preference_tags(
        cls,
        preference_tags: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        expected_categories = set(PREFERENCE_TAG_CATEGORIES)

        if set(preference_tags) != expected_categories:
            raise ValueError(
                "preference_tags must contain exactly: "
                + ", ".join(PREFERENCE_TAG_CATEGORIES),
            )

        normalized_tags: dict[str, list[str]] = {}

        for category in PREFERENCE_TAG_CATEGORIES:
            tags = [tag.strip() for tag in preference_tags[category]]

            if any(not tag for tag in tags):
                raise ValueError("Preference tags cannot be empty.")

            if len(tags) != len(set(tags)):
                raise ValueError(
                    f"Duplicate tags are not allowed in {category}.",
                )

            normalized_tags[category] = tags

        return normalized_tags
