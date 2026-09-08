from dataclasses import replace

from app.models.decision_change import ProfileMergeResult, profile_mutation_causes
from app.models.profile import LivingProfile
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicStatus
from app.services.conversation_manager import conversation_manager
from app.services.geographic_resolution import (
    GeographicResolutionResult,
    geographic_resolver,
)
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
        if profile.work_location != previous_profile.work_location:
            self._clear_work_grounding(profile)
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

    @staticmethod
    def _clear_work_grounding(profile: LivingProfile) -> None:
        profile.geographic_identity = None
        profile.geographic_precision = None
        profile.geographic_status = GeographicStatus.UNRESOLVED
        profile.lng = None
        profile.lat = None

    def delete(
        self,
        conversation_id: str,
    ) -> bool:
        return profile_store.delete(conversation_id)

    def resolve_work_geographic_grounding(
        self,
        conversation_id: str,
        *,
        context_location: str | None,
        api_key: str | None,
    ) -> GeographicResolutionResult:
        profile = self.get(conversation_id)
        if profile is None or not profile.work_location:
            return GeographicResolutionResult(status="UNRESOLVED")

        result = geographic_resolver.resolve(
            profile.work_location,
            context_location,
            api_key,
        )
        if result.status != "GROUNDED":
            return result

        profile.geographic_identity = result.geographic_identity
        profile.geographic_precision = result.geographic_precision
        profile.geographic_status = GeographicStatus.GROUNDED
        profile.lng = result.lng
        profile.lat = result.lat
        profile_store.save(conversation_id, profile)
        return result

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
