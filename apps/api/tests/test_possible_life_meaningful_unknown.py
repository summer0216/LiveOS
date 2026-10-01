import json

from app.models.living_time import LivingTimeRelationship
from app.models.possible_life_personal_meaning import PossibleLifePersonalMeaning
from app.models.profile_patch import LivingProfilePatch
from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    Property,
)
from app.models.work_subject import WorkSubject
from app.services.conversation_manager import conversation_manager
from app.services.living_meaning_service import LivingMeaningService
from app.services.possible_life_admission import possible_life_admission_service
from app.services.possible_life_meaningful_unknown import (
    PossibleLifeMeaningfulUnknownService,
)
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.stores.runtime import (
    living_time_relationship_store,
    possible_life_meaningful_unknown_store,
    possible_life_personal_meaning_store,
    possible_life_store,
    work_subject_store,
)
from tests.ids import uuid_for


class MeaningfulUnknownIntelligence:
    def __init__(
        self,
        *,
        no_candidate: bool = False,
        material: bool = True,
        judgment_reference: str = (
            "一分钟步行通勤满足要求，但住所内部生活条件仍未确认。"
        ),
    ) -> None:
        self.no_candidate = no_candidate
        self.material = material
        self.judgment_reference = judgment_reference
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, **_kwargs) -> str:
        self.prompts.append(prompt)
        if self.no_candidate:
            return "null"
        question = "这套住所夜间室内是否安静？"
        judgment = self.judgment_reference
        if "Judge whether this proposed Unknown" in prompt:
            return json.dumps({
                "question_reference": question,
                "judgment_reference": judgment,
                "current_reality_sufficient": not self.material,
                "material_decision_change": self.material,
                "single_observable_fact": True,
                "impact_without_unsupported_bridge": True,
                "sufficient_dimension": "",
                "plausible_answer_a": "夜间室内安静",
                "impact_a": "短通勤之外，住所也支持夜间休息",
                "plausible_answer_b": "夜间室内持续有明显噪音",
                "impact_b": "噪音形成新的日常生活限制",
                "reason": "两种可观察答案会形成不同的居住意义。",
            }, ensure_ascii=False)
        assert "POSSIBLE_LIFE_ID" in prompt
        assert "1min WALKING" in prompt
        assert "AMAP_DIRECTION_API" in prompt
        assert "<= 30min" in prompt
        assert "一分钟步行通勤让工作与生活紧密衔接。" in prompt
        return json.dumps({
            "unknown_fact": "NIGHT_INDOOR_SOUND",
            "question": question,
            "why_it_matters": "不同答案会增加或排除夜间休息这一生活限制。",
            "meaning_reference": "一分钟步行通勤让工作与生活紧密衔接。",
            "judgment_reference": judgment,
            "grounding": [
                {"fact": "LIVING_TIME", "value": "1min WALKING"},
                {"fact": "COMMUTE_REQUIREMENT", "value": "<= 30min"},
            ],
        }, ensure_ascii=False)


def authoritative_possible_life(
    conversation_id: str,
    title: str,
    *,
    current_judgment: str | None = (
        "一分钟步行通勤满足要求，但住所内部生活条件仍未确认。"
    ),
):
    conversation_manager.get_or_create(conversation_id)
    subject = work_subject_store.save(
        conversation_id,
        WorkSubject(
            identity="融科资讯中心",
            geographic_identity="北京市海淀区融科资讯中心",
            geographic_precision="PLACE",
            geographic_status="GROUNDED",
            lng=116.326178,
            lat=39.984098,
        ),
    )
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(commute_minutes=30),
        latest_insights=[],
    )
    residence = property_manager.create(
        conversation_id,
        Property(
            title=title,
            geographic_identity=f"北京市海淀区{title}",
            geographic_precision=GeographicPrecision.COMMUNITY,
            geographic_status=GeographicStatus.GROUNDED,
            lng=116.28,
            lat=39.98,
            commute_minutes=99,
            commute_mode=CommuteMode.PUBLIC_TRANSIT,
            current_judgment=current_judgment,
            current_judgment_state_hash=(
                "existing-property-judgment" if current_judgment else None
            ),
        ),
    )
    relationship = living_time_relationship_store.save(
        conversation_id,
        LivingTimeRelationship(
            residence_property_id=residence.id or "",
            residence_identity=title,
            residence_geographic_identity=residence.geographic_identity or "",
            work_subject_identity=subject.identity,
            work_geographic_identity=subject.geographic_identity,
            travel_minutes=1,
            travel_mode=CommuteMode.WALKING,
            evidence_source="AMAP_DIRECTION_API",
            evidence_reference="https://restapi.amap.com/v5/direction/walking",
        ),
    )
    possible_life = possible_life_admission_service.admit(
        conversation_id, residence.id or "",
    )
    assert possible_life is not None
    meaning = possible_life_personal_meaning_store.save(
        conversation_id,
        PossibleLifePersonalMeaning(
            id=uuid_for(f"{conversation_id}-meaning"),
            possible_life_id=possible_life.id,
            meaning="一分钟步行通勤让工作与生活紧密衔接。",
            living_time_residence_property_id=relationship.residence_property_id,
            actual_travel_minutes=relationship.travel_minutes,
            actual_travel_mode=relationship.travel_mode,
            route_evidence_source=relationship.evidence_source,
            route_evidence_reference=relationship.evidence_reference,
            requirement_reference=possible_life.personal_meaning_reference,
            maximum_commute_minutes=30,
            requirement_satisfied=True,
        ),
    )
    return residence, relationship, possible_life, meaning


def test_focused_possible_life_persists_meaningful_unknown_without_mutation() -> None:
    conversation_id = uuid_for("focused-possible-life-meaningful-unknown")
    residence, relationship, possible_life, meaning = authoritative_possible_life(
        conversation_id, "融科·昆仑巢",
    )
    possible_life_before = possible_life_store.get(conversation_id, possible_life.id)
    meaning_before = possible_life_personal_meaning_store.get(
        conversation_id, possible_life.id,
    )
    residence_before = property_manager.get_scoped(residence.id or "", conversation_id)
    relationship_before = living_time_relationship_store.get(
        conversation_id, residence.id or "",
    )
    intelligence = MeaningfulUnknownIntelligence()
    service = PossibleLifeMeaningfulUnknownService(
        meaningfulness=LivingMeaningService(intelligence=intelligence),
    )

    unknown = service.form(conversation_id, possible_life.id)

    assert unknown is not None
    assert unknown.possible_life_id == possible_life.id
    assert unknown.personal_meaning_id == meaning.id
    assert possible_life_meaningful_unknown_store.get(
        conversation_id, possible_life.id,
    ) == unknown
    assert possible_life_store.get(conversation_id, possible_life.id) == possible_life_before
    assert possible_life_personal_meaning_store.get(
        conversation_id, possible_life.id,
    ) == meaning_before
    assert property_manager.get_scoped(
        residence.id or "", conversation_id,
    ) == residence_before
    assert living_time_relationship_store.get(
        conversation_id, residence.id or "",
    ) == relationship_before == relationship
    assert len(intelligence.prompts) == 2


def test_generic_missing_data_does_not_create_possible_life_unknown() -> None:
    conversation_id = uuid_for("possible-life-generic-missing-data")
    _, _, possible_life, _ = authoritative_possible_life(
        conversation_id, "新科祥园",
    )
    service = PossibleLifeMeaningfulUnknownService(
        meaningfulness=LivingMeaningService(
            intelligence=MeaningfulUnknownIntelligence(no_candidate=True),
        ),
    )

    assert service.form(conversation_id, possible_life.id) is None
    assert possible_life_meaningful_unknown_store.get(
        conversation_id, possible_life.id,
    ) is None


def test_possible_life_unknown_does_not_require_property_judgment() -> None:
    conversation_id = uuid_for("possible-life-unknown-without-property-judgment")
    residence, relationship, possible_life, meaning = authoritative_possible_life(
        conversation_id,
        "融科·昆仑巢",
        current_judgment=None,
    )
    intelligence = MeaningfulUnknownIntelligence(
        judgment_reference=meaning.meaning,
    )
    service = PossibleLifeMeaningfulUnknownService(
        meaningfulness=LivingMeaningService(intelligence=intelligence),
    )

    unknown = service.form(conversation_id, possible_life.id)

    assert unknown is not None
    assert unknown.possible_life_id == possible_life.id
    assert unknown.personal_meaning_id == meaning.id
    assert possible_life_meaningful_unknown_store.get(
        conversation_id, possible_life.id,
    ) == unknown
    assert property_manager.get_scoped(
        residence.id or "", conversation_id,
    ) == residence
    assert possible_life_store.get(conversation_id, possible_life.id) == possible_life
    assert possible_life_personal_meaning_store.get(
        conversation_id, possible_life.id,
    ) == meaning
    assert living_time_relationship_store.get(
        conversation_id, residence.id or "",
    ) == relationship
    assert all(meaning.meaning in prompt for prompt in intelligence.prompts)


def test_non_material_possible_life_unknown_is_rejected_without_judgment() -> None:
    conversation_id = uuid_for("non-material-possible-life-unknown")
    _, _, possible_life, meaning = authoritative_possible_life(
        conversation_id,
        "新科祥园",
        current_judgment=None,
    )
    service = PossibleLifeMeaningfulUnknownService(
        meaningfulness=LivingMeaningService(
            intelligence=MeaningfulUnknownIntelligence(
                material=False,
                judgment_reference=meaning.meaning,
            ),
        ),
    )

    assert service.form(conversation_id, possible_life.id) is None
    assert possible_life_meaningful_unknown_store.get(
        conversation_id, possible_life.id,
    ) is None
