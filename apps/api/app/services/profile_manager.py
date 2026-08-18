from app.models.profile import LivingProfile
from app.models.profile_patch import LivingProfilePatch
from app.services.conversation_manager import conversation_manager
from app.stores.runtime import profile_store


class ProfileManager:
    def get_or_create(
        self,
        conversation_id: str,
    ) -> LivingProfile:
        profile = profile_store.get(conversation_id)
        if profile is not None:
            return profile
        conversation_manager.get_or_create(conversation_id)
        return profile_store.save(conversation_id, LivingProfile())

    def get(
        self,
        conversation_id: str,
    ) -> LivingProfile | None:
        return profile_store.get(conversation_id)

    def merge(
        self,
        conversation_id: str,
        patch: LivingProfilePatch,
        latest_insights: list[str],
    ) -> tuple[LivingProfile, bool]:
        profile = self.get_or_create(conversation_id)
        previous_values = (
            profile.work_location,
            profile.budget,
            profile.commute_minutes,
            profile.preferred_city,
            profile.family_size,
            profile.has_pet,
        )

        profile.apply_patch(patch)
        profile.latest_insights = latest_insights.copy()

        saved_profile = profile_store.save(conversation_id, profile)
        current_values = (
            saved_profile.work_location,
            saved_profile.budget,
            saved_profile.commute_minutes,
            saved_profile.preferred_city,
            saved_profile.family_size,
            saved_profile.has_pet,
        )

        return saved_profile, previous_values != current_values

    def delete(
        self,
        conversation_id: str,
    ) -> bool:
        return profile_store.delete(conversation_id)

    def update_tags(
        self,
        conversation_id: str,
        preference_tags: dict[str, list[str]],
    ) -> LivingProfile | None:
        profile = self.get(conversation_id)

        if profile is None:
            return None

        profile.preference_tags = {
            category: tags.copy() for category, tags in preference_tags.items()
        }

        return profile_store.save(conversation_id, profile)


profile_manager = ProfileManager()
