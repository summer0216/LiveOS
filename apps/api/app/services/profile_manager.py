from dataclasses import replace

from app.models.decision_change import ProfileMergeResult, profile_mutation_causes
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
    ) -> ProfileMergeResult:
        profile = self.get_or_create(conversation_id)
        previous_profile = replace(profile)

        profile.apply_patch(patch)
        profile.latest_insights = latest_insights.copy()

        saved_profile = profile_store.save(conversation_id, profile)
        causes = profile_mutation_causes(
            previous_profile,
            saved_profile,
            patch.clear_fields,
        )

        return ProfileMergeResult(
            profile=saved_profile,
            changed=bool(causes),
            causes=causes,
        )

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
