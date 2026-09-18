import re
from dataclasses import replace

from app.models.decision_change import ProfileMergeResult, profile_mutation_causes
from app.models.profile import LivingProfile
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicStatus
from app.services.conversation_manager import conversation_manager
from app.services.geographic_resolution import (
    GeographicResolutionResult,
    geographic_resolver,
    identity_explicitly_names_city,
)
from app.stores.runtime import profile_store

_LEGACY_NANSHAN_WORK_GROUNDING = (
    "南山科技园",
    "深圳市南山区南山科技园",
    GeographicStatus.GROUNDED,
    113.947,
    22.541,
)


def _work_identity_within_context(identity: str, context: str | None) -> str:
    if not context:
        return identity
    compact_identity = "".join(identity.split())
    compact_context = "".join(context.split())
    city = compact_context.removesuffix("市")
    match = re.match(rf"^(?:{re.escape(compact_context)}|{re.escape(city)})(?:的)?(.+)$", compact_identity)
    return match.group(1) if match is not None else identity


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

    @staticmethod
    def needs_work_geographic_resolution(profile: LivingProfile) -> bool:
        if not profile.work_location:
            return False
        if profile.geographic_status == GeographicStatus.UNRESOLVED:
            return True
        return (
            profile.work_location,
            profile.geographic_identity,
            profile.geographic_status,
            profile.lng,
            profile.lat,
        ) == _LEGACY_NANSHAN_WORK_GROUNDING

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

        if self.needs_work_geographic_resolution(profile) and (
            profile.geographic_status == GeographicStatus.GROUNDED
        ):
            self._clear_work_grounding(profile)
            profile_store.save(conversation_id, profile)

        result = geographic_resolver.resolve(
            profile.work_location,
            None,
            api_key,
        )
        explicit_city = identity_explicitly_names_city(profile.work_location, result)
        if result.status != "GROUNDED" and not explicit_city:
            result = geographic_resolver.resolve_local_area(
                profile.work_location,
                None,
                api_key,
            )
        if result.status != "GROUNDED" and context_location and not explicit_city:
            contextual_identity = _work_identity_within_context(
                profile.work_location,
                context_location,
            )
            result = geographic_resolver.resolve(
                contextual_identity,
                context_location,
                api_key,
            )
        if result.status != "GROUNDED" and context_location and not explicit_city:
            result = geographic_resolver.resolve_local_area(
                contextual_identity,
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
