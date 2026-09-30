import json

from app.models.living_time import LivingTimeRelationship
from app.models.profile_patch import LivingProfilePatch
from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    Property,
)
from app.models.work_subject import WorkSubject
from app.services.conversation_manager import conversation_manager
from app.services.possible_life_admission import possible_life_admission_service
from app.services.possible_life_personal_meaning import (
    PossibleLifePersonalMeaningService,
)
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.stores.runtime import (
    living_time_relationship_store,
    possible_life_personal_meaning_store,
    work_subject_store,
)
from tests.ids import uuid_for


class GroundedMeaningIntelligence:
    def __init__(self) -> None:
        self.calls = 0

    def generate_json(self, prompt: str, **_kwargs) -> str:
        self.calls += 1
        context = json.loads(prompt.split("Authoritative context:\n", 1)[1])
        living_time = context["living_time"]
        maximum = context["personal_requirement"]["maximum_commute_minutes"]
        satisfied = context["requirement_evaluation"]["satisfied"]
        relation = "满足" if satisfied else "超过"
        return json.dumps({
            "possible_life_id": context["possible_life_id"],
            "meaning": (
                f"实际{living_time['travel_minutes']}分钟"
                f"{living_time['travel_mode']}通勤{relation}{maximum}分钟要求，"
                "这段日常通勤符合当前生活约束。"
            ),
            "grounding": {
                "travel_minutes": living_time["travel_minutes"],
                "travel_mode": living_time["travel_mode"],
                "evidence_source": living_time["evidence_source"],
                "evidence_reference": living_time["evidence_reference"],
                "maximum_commute_minutes": maximum,
                "requirement_satisfied": satisfied,
            },
        }, ensure_ascii=False)


class MissingLivingTimeStore:
    def get(self, *_args) -> None:
        return None


def authoritative_possible_life(
    conversation_id: str,
    title: str,
    *,
    minutes: int,
    property_commute_minutes: int,
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
            commute_minutes=property_commute_minutes,
            commute_mode=CommuteMode.PUBLIC_TRANSIT,
            geographic_identity=f"北京市海淀区{title}",
            geographic_precision=GeographicPrecision.COMMUNITY,
            geographic_status=GeographicStatus.GROUNDED,
            lng=116.28,
            lat=39.98,
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
            travel_minutes=minutes,
            travel_mode=CommuteMode.WALKING,
            evidence_source="AMAP_DIRECTION_API",
            evidence_reference="https://restapi.amap.com/v5/direction/walking",
        ),
    )
    possible_life = possible_life_admission_service.admit(
        conversation_id, residence.id or "",
    )
    assert possible_life is not None
    return residence, relationship, possible_life


def test_possible_life_forms_and_persists_personal_meaning_from_living_time() -> None:
    conversation_id = uuid_for("possible-life-personal-meaning")
    residence, relationship, possible_life = authoritative_possible_life(
        conversation_id,
        "融科昆仑巢",
        minutes=1,
        property_commute_minutes=99,
    )
    intelligence = GroundedMeaningIntelligence()
    service = PossibleLifePersonalMeaningService(intelligence=intelligence)

    meaning = service.form(conversation_id, possible_life.id)

    assert meaning is not None
    assert meaning.possible_life_id == possible_life.id
    assert meaning.actual_travel_minutes == 1
    assert meaning.actual_travel_mode == CommuteMode.WALKING
    assert meaning.route_evidence_source == "AMAP_DIRECTION_API"
    assert meaning.maximum_commute_minutes == 30
    assert meaning.requirement_satisfied is True
    assert residence.commute_minutes == 99
    assert living_time_relationship_store.get(
        conversation_id, residence.id or "",
    ) == relationship
    assert possible_life_personal_meaning_store.get(
        conversation_id, possible_life.id,
    ) == meaning
    assert property_manager.get_scoped(
        residence.id or "", conversation_id,
    ).living_meaning is None


def test_missing_authoritative_living_time_does_not_fabricate_meaning() -> None:
    conversation_id = uuid_for("possible-life-meaning-missing-living-time")
    _, _, possible_life = authoritative_possible_life(
        conversation_id, "新科祥园", minutes=5, property_commute_minutes=2,
    )
    intelligence = GroundedMeaningIntelligence()
    service = PossibleLifePersonalMeaningService(
        relationships=MissingLivingTimeStore(),
        intelligence=intelligence,
    )

    assert service.form(conversation_id, possible_life.id) is None
    assert intelligence.calls == 0
    assert possible_life_personal_meaning_store.get(
        conversation_id, possible_life.id,
    ) is None


def test_multiple_possible_lives_hold_distinct_personal_meanings() -> None:
    conversation_id = uuid_for("distinct-possible-life-personal-meanings")
    _, _, first = authoritative_possible_life(
        conversation_id, "融科昆仑巢", minutes=1, property_commute_minutes=40,
    )
    _, _, second = authoritative_possible_life(
        conversation_id, "新科祥园", minutes=5, property_commute_minutes=40,
    )
    service = PossibleLifePersonalMeaningService(
        intelligence=GroundedMeaningIntelligence(),
    )

    first_meaning = service.form(conversation_id, first.id)
    second_meaning = service.form(conversation_id, second.id)

    assert first_meaning is not None and second_meaning is not None
    assert first_meaning.possible_life_id != second_meaning.possible_life_id
    assert first_meaning.meaning != second_meaning.meaning
    assert {
        item.possible_life_id
        for item in possible_life_personal_meaning_store.list(conversation_id)
    } == {first.id, second.id}
