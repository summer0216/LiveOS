from app.models.profile import LivingProfile
from app.models.profile_patch import LivingProfilePatch


class ProfileManager:
    def __init__(self) -> None:
        self._profiles: dict[str, LivingProfile] = {}

    def get_or_create(
        self,
        conversation_id: str,
    ) -> LivingProfile:
        profile = self._profiles.get(conversation_id)

        if profile is None:
            profile = LivingProfile()
            self._profiles[conversation_id] = profile

        return profile

    def get(
        self,
        conversation_id: str,
    ) -> LivingProfile | None:
        return self._profiles.get(conversation_id)

    def merge(
        self,
        conversation_id: str,
        patch: LivingProfilePatch,
    ) -> LivingProfile:
        profile = self.get_or_create(conversation_id)

        profile.apply_patch(patch)

        return profile

    def delete(
        self,
        conversation_id: str,
    ) -> None:
        self._profiles.pop(conversation_id, None)


profile_manager = ProfileManager()
