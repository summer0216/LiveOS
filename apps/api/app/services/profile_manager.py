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
    ) -> LivingProfile:
        profile = self.get_or_create(conversation_id)

        profile.apply_patch(patch)
        profile.latest_insights = latest_insights.copy()

        return profile_store.save(conversation_id, profile)

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
