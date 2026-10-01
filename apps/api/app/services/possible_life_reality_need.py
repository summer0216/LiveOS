import hashlib
import json
from uuid import uuid4

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
from app.models.property import GeographicStatus
from app.models.reality_need import RealityNeed, RealityNeedResolutionMode
from app.services.living_meaning_service import LivingMeaningService
from app.services.profile_manager import ProfileManager, profile_manager
from app.services.property_manager import PropertyManager, property_manager
from app.stores.persistent import (
    LivingTimeRelationshipStore,
    PossibleLifeMeaningfulUnknownStore,
    PossibleLifePersonalMeaningStore,
    PossibleLifeStore,
    RealityNeedStore,
    WorkSubjectStore,
)
from app.stores.runtime import (
    living_time_relationship_store,
    possible_life_meaningful_unknown_store,
    possible_life_personal_meaning_store,
    possible_life_store,
    reality_need_store,
    work_subject_store,
)


class PossibleLifeRealityNeedService:
    def __init__(
        self,
        *,
        possible_lives: PossibleLifeStore = possible_life_store,
        unknowns: PossibleLifeMeaningfulUnknownStore = (
            possible_life_meaningful_unknown_store
        ),
        meanings: PossibleLifePersonalMeaningStore = (
            possible_life_personal_meaning_store
        ),
        relationships: LivingTimeRelationshipStore = living_time_relationship_store,
        subjects: WorkSubjectStore = work_subject_store,
        needs: RealityNeedStore = reality_need_store,
        properties: PropertyManager = property_manager,
        profiles: ProfileManager = profile_manager,
        intelligence: AIClient = ai_client,
    ) -> None:
        self._possible_lives = possible_lives
        self._unknowns = unknowns
        self._meanings = meanings
        self._relationships = relationships
        self._subjects = subjects
        self._needs = needs
        self._properties = properties
        self._profiles = profiles
        self._intelligence = intelligence

    def form(
        self, conversation_id: str, possible_life_id: str, meaningful_unknown_id: str,
    ) -> RealityNeed | None:
        possible_life = self._possible_lives.get(conversation_id, possible_life_id)
        unknown = self._unknowns.get(conversation_id, possible_life_id)
        meaning = self._meanings.get(conversation_id, possible_life_id)
        if (
            possible_life is None
            or unknown is None
            or meaning is None
            or unknown.id != meaningful_unknown_id
            or unknown.possible_life_id != possible_life.id
            or unknown.personal_meaning_id != meaning.id
            or meaning.possible_life_id != possible_life.id
        ):
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
            or possible_life.residence_property_id != relationship.residence_property_id
            or relationship.residence_geographic_identity
            != residence.geographic_identity
            or relationship.work_subject_identity != subject.identity
            or relationship.work_geographic_identity != subject.geographic_identity
            or not relationship.evidence_source
            or not relationship.evidence_reference
        ):
            return None

        basis = LivingMeaningService._basis(residence, profile)
        admitted_keys = {
            "HOME_IDENTITY", "LAYOUT_REALITY", "INDEPENDENT_BATHROOM_REALITY",
            "TENANCY_MODE_REALITY", "GROCERY_WALK", "RENT_REALITY",
            "EXTERNAL_RENT_OBSERVATION", "INDEPENDENT_KITCHEN_REALITY",
            "INDOOR_SOUND_OBSERVATION",
        }
        admitted_reality = {
            key: value for key, value in basis.items() if key in admitted_keys
        }
        admitted_reality.update({
            "HOME_GEOGRAPHIC_IDENTITY": residence.geographic_identity,
            "WORK_IDENTITY": subject.identity,
            "WORK_GEOGRAPHIC_IDENTITY": subject.geographic_identity,
            "LIVING_TIME": (
                f"{relationship.travel_minutes}min {relationship.travel_mode.value}"
            ),
            "LIVING_TIME_EVIDENCE_SOURCE": relationship.evidence_source,
            "LIVING_TIME_EVIDENCE_REFERENCE": relationship.evidence_reference,
        })
        known_fact_keys = admitted_reality.keys() - {
            "LIVING_TIME_EVIDENCE_SOURCE", "LIVING_TIME_EVIDENCE_REFERENCE",
        }
        context = {
            "possible_life_id": possible_life.id,
            "meaningful_unknown_id": unknown.id,
            "question": unknown.question,
            "why_it_matters": unknown.why_it_matters,
            "unknown_state_hash": unknown.state_hash,
            "personal_meaning_id": meaning.id,
            "personal_meaning": meaning.meaning,
            "admitted_reality": admitted_reality,
            "personal_requirements": {
                "layout": profile.layout_requirement,
                "maximum_commute_minutes": profile.commute_minutes,
            },
        }
        state_hash = hashlib.sha256(json.dumps(
            context, ensure_ascii=False, sort_keys=True,
        ).encode()).hexdigest()
        existing = self._needs.get(conversation_id, unknown.id)
        if existing is not None and existing.state_hash == state_hash:
            return existing

        prompt = (
            "Identify the one concrete Reality needed to resolve this already "
            "admitted Meaningful Unknown. This is not an Action or provider choice. "
            "Return a JSON object with possible_life_id, meaningful_unknown_id, "
            "unknown_reference (exact question), needed_reality (specific fact, "
            "not the question), resolution_mode, known_reality_reference. "
            "Modes: ALREADY_KNOWN only when an admitted_reality fact directly "
            "answers the question; cite its exact key. USER_ANSWERABLE when the "
            "user can directly provide the fact from existing knowledge in "
            "Conversation, without a new real-world observation. "
            "REAL_WORLD_CONTACT when obtaining the fact requires a new "
            "observation or external contact; this does not create an Action. "
            "For the latter two modes known_reality_reference must be null. "
            "Do not infer from missing fields alone or invent an admitted fact. "
            "Return null if a concrete material need cannot be identified.\n"
            f"Context: {json.dumps(context, ensure_ascii=False, sort_keys=True)}"
        )
        try:
            proposed = json.loads(self._intelligence.generate_json(
                prompt, model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
            ))
        except (RuntimeError, TypeError, ValueError, json.JSONDecodeError):
            return None
        if not isinstance(proposed, dict):
            return None
        needed_reality = proposed.get("needed_reality")
        if (
            proposed.get("possible_life_id") != possible_life.id
            or proposed.get("meaningful_unknown_id") != unknown.id
            or proposed.get("unknown_reference") != unknown.question
            or not isinstance(needed_reality, str)
            or not needed_reality.strip()
            or needed_reality.strip() == unknown.question.strip()
            or len(needed_reality) > 500
        ):
            return None
        try:
            mode = RealityNeedResolutionMode(proposed.get("resolution_mode"))
        except (TypeError, ValueError):
            return None
        known_reference = proposed.get("known_reality_reference")
        if mode == RealityNeedResolutionMode.ALREADY_KNOWN:
            if not isinstance(known_reference, str) or known_reference not in known_fact_keys:
                return None
        elif known_reference is not None:
            return None
        return self._needs.save(
            conversation_id,
            RealityNeed(
                id=existing.id if existing is not None else str(uuid4()),
                possible_life_id=possible_life.id,
                meaningful_unknown_id=unknown.id,
                needed_reality=needed_reality.strip(),
                resolution_mode=mode,
                known_reality_reference=known_reference,
                state_hash=state_hash,
            ),
        )


possible_life_reality_need_service = PossibleLifeRealityNeedService()
