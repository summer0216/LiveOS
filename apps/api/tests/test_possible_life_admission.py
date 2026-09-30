from dataclasses import fields

import pytest
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
from app.services.living_time_relationship import LivingTimeRelationshipService
from app.services.possible_life_admission import possible_life_admission_service
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.services.transit_duration import LivingTimeResult
from app.stores.runtime import (
    living_time_relationship_store,
    possible_life_store,
    work_subject_store,
)
from tests.ids import uuid_for


class GroundedRoute:
    def calculate_living_time(self, **_kwargs) -> LivingTimeResult:
        return LivingTimeResult(
            25,
            CommuteMode.PUBLIC_TRANSIT,
            evidence_source="AMAP_DIRECTION_API",
            evidence_reference=(
                "https://restapi.amap.com/v5/direction/transit/integrated"
            ),
        )


def admit_work_subject(conversation_id: str) -> WorkSubject:
    conversation_manager.get_or_create(conversation_id)
    return work_subject_store.save(
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


def admit_residence(
    conversation_id: str,
    title: str,
    *,
    lng: float,
) -> Property:
    residence = property_manager.create(
        conversation_id,
        Property(
            title=title,
            geographic_identity=f"北京市海淀区{title}",
            geographic_precision=GeographicPrecision.COMMUNITY,
            geographic_status=GeographicStatus.GROUNDED,
            lng=lng,
            lat=39.98,
        ),
    )
    return residence


def admit_commute_meaning(conversation_id: str, minutes: int = 30) -> None:
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(commute_minutes=minutes),
        latest_insights=[],
    )


def admit_living_time(
    conversation_id: str,
    residence: Property,
    work_subject: WorkSubject,
    minutes: int = 25,
) -> LivingTimeRelationship:
    return living_time_relationship_store.save(
        conversation_id,
        LivingTimeRelationship(
            residence_property_id=residence.id or "",
            residence_identity=residence.title or "",
            residence_geographic_identity=residence.geographic_identity or "",
            work_subject_identity=work_subject.identity,
            work_geographic_identity=work_subject.geographic_identity,
            travel_minutes=minutes,
            travel_mode=CommuteMode.PUBLIC_TRANSIT,
            evidence_source="AMAP_DIRECTION_API",
            evidence_reference="https://restapi.amap.com/v5/direction/transit/integrated",
        ),
    )


def test_grounded_references_admit_authoritative_possible_life() -> None:
    conversation_id = uuid_for("authoritative-possible-life")
    work_subject = admit_work_subject(conversation_id)
    admit_commute_meaning(conversation_id)
    residence = admit_residence(
        conversation_id, "西山庭院", lng=116.286,
    )
    living_time = admit_living_time(conversation_id, residence, work_subject)

    possible_life = possible_life_admission_service.admit(
        conversation_id, residence.id or "",
    )

    assert possible_life is not None
    assert possible_life.residence_property_id == residence.id
    assert possible_life.living_time_residence_property_id == (
        living_time.residence_property_id
    )
    assert possible_life.personal_meaning_reference == "living_profile.commute_minutes"
    assert work_subject_store.get(conversation_id) == work_subject
    assert living_time_relationship_store.get(
        conversation_id, residence.id or "",
    ) == living_time
    assert property_manager.get_scoped(residence.id or "", conversation_id) == residence
    assert {field.name for field in fields(possible_life)} == {
        "id",
        "work_subject_owner_id",
        "residence_property_id",
        "living_time_residence_property_id",
        "personal_meaning_reference",
    }


def test_living_time_admission_organizes_possible_life() -> None:
    conversation_id = uuid_for("living-time-organizes-possible-life")
    work_subject = admit_work_subject(conversation_id)
    admit_commute_meaning(conversation_id)
    residence = admit_residence(conversation_id, "西山庭院", lng=116.286)
    service = LivingTimeRelationshipService(
        relationships=living_time_relationship_store,
        transit=GroundedRoute(),
    )

    admission = service.establish(
        conversation_id=conversation_id,
        residence=residence,
        work_subject=work_subject,
        api_key="test-key",
        commute_requirement_minutes=30,
    )

    assert admission is not None
    possible_lives = possible_life_store.list(conversation_id)
    assert len(possible_lives) == 1
    assert possible_lives[0].residence_property_id == residence.id
    assert possible_lives[0].living_time_residence_property_id == residence.id


@pytest.mark.parametrize(
        "missing",
        ["work_subject", "grounded_residence", "living_time", "personal_meaning"],
)
def test_missing_required_reality_or_relationship_does_not_admit(
    missing: str,
) -> None:
    conversation_id = uuid_for(f"possible-life-missing-{missing}")
    work_subject = (
        None if missing == "work_subject" else admit_work_subject(conversation_id)
    )
    if missing != "personal_meaning":
        admit_commute_meaning(conversation_id)
    residence = admit_residence(
        conversation_id,
        "西山庭院",
        lng=116.286,
    )
    if missing == "grounded_residence":
        residence = property_manager.update_geographic_grounding(
            residence.id or "",
            conversation_id,
            geographic_identity=None,
            geographic_precision=None,
            geographic_status=GeographicStatus.UNRESOLVED,
            lng=None,
            lat=None,
        ) or residence
    if missing != "living_time" and work_subject is not None:
        admit_living_time(conversation_id, residence, work_subject)

    assert possible_life_admission_service.admit(
        conversation_id, residence.id or "",
    ) is None
    assert possible_life_store.list(conversation_id) == []


def test_multiple_residences_form_distinct_possible_lives() -> None:
    conversation_id = uuid_for("multiple-authoritative-possible-lives")
    work_subject = admit_work_subject(conversation_id)
    admit_commute_meaning(conversation_id)
    first = admit_residence(conversation_id, "西山庭院", lng=116.286)
    second = admit_residence(conversation_id, "新科祥园", lng=116.324)
    admit_living_time(conversation_id, first, work_subject, 25)
    admit_living_time(conversation_id, second, work_subject, 8)

    first_life = possible_life_admission_service.admit(
        conversation_id, first.id or "",
    )
    second_life = possible_life_admission_service.admit(
        conversation_id, second.id or "",
    )

    assert first_life is not None and second_life is not None
    assert first_life.id != second_life.id
    assert first_life.work_subject_owner_id == second_life.work_subject_owner_id
    assert {
        item.residence_property_id for item in possible_life_store.list(conversation_id)
    } == {first.id, second.id}
