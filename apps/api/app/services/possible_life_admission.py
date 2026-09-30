from uuid import uuid4

from app.models.possible_life import PossibleLife
from app.models.property import GeographicStatus
from app.services.profile_manager import ProfileManager, profile_manager
from app.services.property_manager import PropertyManager, property_manager
from app.stores.persistent import PossibleLifeStore
from app.stores.runtime import (
    living_time_relationship_store,
    possible_life_store,
    work_subject_store,
)


class PossibleLifeAdmissionService:
    def __init__(
        self,
        *,
        properties: PropertyManager = property_manager,
        profiles: ProfileManager = profile_manager,
        possible_lives: PossibleLifeStore = possible_life_store,
    ) -> None:
        self._properties = properties
        self._profiles = profiles
        self._possible_lives = possible_lives

    def admit(self, conversation_id: str, residence_property_id: str) -> PossibleLife | None:
        residence = self._properties.get_scoped(
            residence_property_id, conversation_id,
        )
        work_subject = work_subject_store.get(conversation_id)
        profile = self._profiles.get(conversation_id)
        living_time = living_time_relationship_store.get(
            conversation_id, residence_property_id,
        )
        if (
            residence is None
            or residence.geographic_status != GeographicStatus.GROUNDED
            or not residence.geographic_identity
            or residence.lng is None
            or residence.lat is None
            or work_subject is None
            or living_time is None
            or profile is None
            or profile.commute_minutes is None
            or profile.commute_minutes < 1
            or living_time.residence_property_id != residence.id
            or living_time.residence_geographic_identity
            != residence.geographic_identity
            or living_time.work_subject_identity != work_subject.identity
            or living_time.work_geographic_identity
            != work_subject.geographic_identity
        ):
            return None
        owner_id = self._possible_lives.owner_id(conversation_id)
        if owner_id is None:
            return None
        return self._possible_lives.save(
            conversation_id,
            PossibleLife(
                id=str(uuid4()),
                work_subject_owner_id=owner_id,
                residence_property_id=residence.id or "",
                living_time_residence_property_id=living_time.residence_property_id,
                personal_meaning_reference="living_profile.commute_minutes",
            ),
        )


possible_life_admission_service = PossibleLifeAdmissionService()
