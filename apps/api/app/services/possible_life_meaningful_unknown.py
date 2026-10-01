import hashlib
import json
from uuid import uuid4

from app.models.possible_life_meaningful_unknown import PossibleLifeMeaningfulUnknown
from app.models.property import GeographicStatus
from app.services.living_meaning_service import (
    LivingMeaningService,
    living_meaning_service,
)
from app.services.profile_manager import ProfileManager, profile_manager
from app.services.property_manager import PropertyManager, property_manager
from app.stores.persistent import (
    LivingTimeRelationshipStore,
    PossibleLifeMeaningfulUnknownStore,
    PossibleLifePersonalMeaningStore,
    PossibleLifeStore,
    WorkSubjectStore,
)
from app.stores.runtime import (
    living_time_relationship_store,
    possible_life_meaningful_unknown_store,
    possible_life_personal_meaning_store,
    possible_life_store,
    work_subject_store,
)


class PossibleLifeMeaningfulUnknownService:
    def __init__(
        self,
        *,
        possible_lives: PossibleLifeStore = possible_life_store,
        meanings: PossibleLifePersonalMeaningStore = possible_life_personal_meaning_store,
        relationships: LivingTimeRelationshipStore = living_time_relationship_store,
        unknowns: PossibleLifeMeaningfulUnknownStore = (
            possible_life_meaningful_unknown_store
        ),
        subjects: WorkSubjectStore = work_subject_store,
        properties: PropertyManager = property_manager,
        profiles: ProfileManager = profile_manager,
        meaningfulness: LivingMeaningService = living_meaning_service,
    ) -> None:
        self._possible_lives = possible_lives
        self._meanings = meanings
        self._relationships = relationships
        self._unknowns = unknowns
        self._subjects = subjects
        self._properties = properties
        self._profiles = profiles
        self._meaningfulness = meaningfulness

    def form(
        self, conversation_id: str, possible_life_id: str,
    ) -> PossibleLifeMeaningfulUnknown | None:
        possible_life = self._possible_lives.get(conversation_id, possible_life_id)
        meaning = self._meanings.get(conversation_id, possible_life_id)
        if possible_life is None or meaning is None:
            return None
        residence = self._properties.get_scoped(
            possible_life.residence_property_id, conversation_id,
        )
        relationship = self._relationships.get(
            conversation_id, possible_life.living_time_residence_property_id,
        )
        subject = self._subjects.get(conversation_id)
        profile = self._profiles.get(conversation_id)
        if (
            residence is None
            or residence.geographic_status != GeographicStatus.GROUNDED
            or not residence.geographic_identity
            or relationship is None
            or subject is None
            or profile is None
            or profile.commute_minutes is None
            or possible_life.residence_property_id != residence.id
            or possible_life.living_time_residence_property_id
            != relationship.residence_property_id
            or meaning.possible_life_id != possible_life.id
            or meaning.living_time_residence_property_id
            != relationship.residence_property_id
            or meaning.actual_travel_minutes != relationship.travel_minutes
            or meaning.actual_travel_mode != relationship.travel_mode
            or meaning.route_evidence_source != relationship.evidence_source
            or meaning.route_evidence_reference != relationship.evidence_reference
            or not relationship.evidence_source
            or not relationship.evidence_reference
            or meaning.requirement_reference
            != possible_life.personal_meaning_reference
            or meaning.maximum_commute_minutes != profile.commute_minutes
            or meaning.requirement_satisfied
            != (relationship.travel_minutes <= profile.commute_minutes)
            or relationship.residence_identity != residence.title
            or relationship.residence_geographic_identity
            != residence.geographic_identity
            or relationship.work_subject_identity != subject.identity
            or relationship.work_geographic_identity
            != subject.geographic_identity
        ):
            return None

        basis = self._meaningfulness._basis(residence, profile)
        basis.pop("WORK_IDENTITY", None)
        basis.pop("WORK_COMMUTE", None)
        basis.update({
            "POSSIBLE_LIFE_ID": possible_life.id,
            "HOME_GEOGRAPHIC_IDENTITY": residence.geographic_identity,
            "WORK_IDENTITY": subject.identity,
            "WORK_GEOGRAPHIC_IDENTITY": subject.geographic_identity,
            "LIVING_TIME": (
                f"{relationship.travel_minutes}min {relationship.travel_mode.value}"
            ),
            "LIVING_TIME_EVIDENCE_SOURCE": relationship.evidence_source,
            "LIVING_TIME_EVIDENCE_REFERENCE": relationship.evidence_reference,
            "COMMUTE_REQUIREMENT": f"<= {profile.commute_minutes}min",
            "COMMUTE_REQUIREMENT_EVALUATION": (
                "SATISFIED" if meaning.requirement_satisfied else "NOT_SATISFIED"
            ),
        })
        judgment_context = residence.current_judgment or meaning.meaning
        state_hash = hashlib.sha256(json.dumps(
            {
                "version": self._meaningfulness.unknown_version,
                "possible_life_id": possible_life.id,
                "personal_meaning_id": meaning.id,
                "personal_meaning": meaning.meaning,
                "current_judgment": judgment_context,
                "basis": basis,
            },
            ensure_ascii=False,
            sort_keys=True,
        ).encode()).hexdigest()
        existing = self._unknowns.get(conversation_id, possible_life.id)
        if existing is not None and existing.state_hash == state_hash:
            return existing
        candidate = self._meaningfulness._generate_meaningful_unknown(
            basis,
            meaning.meaning,
            judgment_context,
        )
        if candidate is None:
            return None
        return self._unknowns.save(
            conversation_id,
            PossibleLifeMeaningfulUnknown(
                id=existing.id if existing is not None else str(uuid4()),
                possible_life_id=possible_life.id,
                personal_meaning_id=meaning.id,
                question=candidate[0],
                why_it_matters=candidate[1],
                state_hash=state_hash,
            ),
        )


possible_life_meaningful_unknown_service = PossibleLifeMeaningfulUnknownService()
