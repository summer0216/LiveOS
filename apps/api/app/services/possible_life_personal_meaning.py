import json
from uuid import uuid4

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
from app.models.possible_life_personal_meaning import PossibleLifePersonalMeaning
from app.models.property import GeographicStatus
from app.services.profile_manager import ProfileManager, profile_manager
from app.services.property_manager import PropertyManager, property_manager
from app.stores.persistent import (
    LivingTimeRelationshipStore,
    PossibleLifePersonalMeaningStore,
    PossibleLifeStore,
)
from app.stores.runtime import (
    living_time_relationship_store,
    possible_life_personal_meaning_store,
    possible_life_store,
    work_subject_store,
)


class PossibleLifePersonalMeaningService:
    def __init__(
        self,
        *,
        possible_lives: PossibleLifeStore = possible_life_store,
        relationships: LivingTimeRelationshipStore = living_time_relationship_store,
        meanings: PossibleLifePersonalMeaningStore = (
            possible_life_personal_meaning_store
        ),
        properties: PropertyManager = property_manager,
        profiles: ProfileManager = profile_manager,
        intelligence: AIClient = ai_client,
    ) -> None:
        self._possible_lives = possible_lives
        self._relationships = relationships
        self._meanings = meanings
        self._properties = properties
        self._profiles = profiles
        self._intelligence = intelligence

    def form(
        self, conversation_id: str, possible_life_id: str,
    ) -> PossibleLifePersonalMeaning | None:
        possible_life = self._possible_lives.get(conversation_id, possible_life_id)
        if possible_life is None:
            return None
        residence = self._properties.get_scoped(
            possible_life.residence_property_id, conversation_id,
        )
        work_subject = work_subject_store.get(conversation_id)
        living_time = self._relationships.get(
            conversation_id, possible_life.living_time_residence_property_id,
        )
        profile = self._profiles.get(conversation_id)
        if (
            residence is None
            or residence.geographic_status != GeographicStatus.GROUNDED
            or not residence.geographic_identity
            or work_subject is None
            or living_time is None
            or profile is None
            or profile.commute_minutes is None
            or profile.commute_minutes < 1
            or possible_life.living_time_residence_property_id
            != living_time.residence_property_id
            or possible_life.residence_property_id != living_time.residence_property_id
            or living_time.residence_geographic_identity
            != residence.geographic_identity
            or living_time.work_subject_identity != work_subject.identity
            or living_time.work_geographic_identity
            != work_subject.geographic_identity
            or not living_time.evidence_source
            or not living_time.evidence_reference
        ):
            return None

        context = {
            "possible_life_id": possible_life.id,
            "residence_identity": residence.title,
            "residence_geographic_identity": residence.geographic_identity,
            "work_subject_identity": work_subject.identity,
            "work_geographic_identity": work_subject.geographic_identity,
            "living_time": {
                "travel_minutes": living_time.travel_minutes,
                "travel_mode": living_time.travel_mode.value,
                "evidence_source": living_time.evidence_source,
                "evidence_reference": living_time.evidence_reference,
            },
            "personal_requirement": {
                "reference": possible_life.personal_meaning_reference,
                "maximum_commute_minutes": profile.commute_minutes,
            },
            "requirement_evaluation": {
                "satisfied": living_time.travel_minutes <= profile.commute_minutes,
            },
        }
        prompt = f"""
Interpret what this authoritative Possible Life means to the user's daily life.
Use the grounded Living Time as Reality and the commute maximum as a Personal
Requirement. The comparison supports interpretation but is not itself the whole
Meaning. Do not recommend, rank, score, or rewrite any supplied Reality.

Return JSON only with exactly:
{{
  "possible_life_id": "exact supplied Possible Life ID",
  "meaning": "one concise Chinese Personal Meaning",
  "grounding": {{
    "travel_minutes": integer,
    "travel_mode": "WALKING or PUBLIC_TRANSIT",
    "evidence_source": "exact supplied source",
    "evidence_reference": "exact supplied reference",
    "maximum_commute_minutes": integer,
    "requirement_satisfied": true or false
  }}
}}

Authoritative context:
{json.dumps(context, ensure_ascii=False, sort_keys=True)}
""".strip()
        try:
            result = json.loads(self._intelligence.generate_json(
                prompt,
                model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                max_output_tokens=384,
            ))
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return None
        expected_grounding = {
            "travel_minutes": living_time.travel_minutes,
            "travel_mode": living_time.travel_mode.value,
            "evidence_source": living_time.evidence_source,
            "evidence_reference": living_time.evidence_reference,
            "maximum_commute_minutes": profile.commute_minutes,
            "requirement_satisfied": (
                living_time.travel_minutes <= profile.commute_minutes
            ),
        }
        if (
            not isinstance(result, dict)
            or set(result) != {"possible_life_id", "meaning", "grounding"}
            or result["possible_life_id"] != possible_life.id
            or not isinstance(result["meaning"], str)
            or not result["meaning"].strip()
            or len(result["meaning"].strip()) > 160
            or result["grounding"] != expected_grounding
        ):
            return None

        return self._meanings.save(
            conversation_id,
            PossibleLifePersonalMeaning(
                id=str(uuid4()),
                possible_life_id=possible_life.id,
                meaning=result["meaning"].strip(),
                living_time_residence_property_id=(
                    living_time.residence_property_id
                ),
                actual_travel_minutes=living_time.travel_minutes,
                actual_travel_mode=living_time.travel_mode,
                route_evidence_source=living_time.evidence_source,
                route_evidence_reference=living_time.evidence_reference,
                requirement_reference=possible_life.personal_meaning_reference,
                maximum_commute_minutes=profile.commute_minutes,
                requirement_satisfied=(
                    living_time.travel_minutes <= profile.commute_minutes
                ),
            ),
        )


possible_life_personal_meaning_service = PossibleLifePersonalMeaningService()
