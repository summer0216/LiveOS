from dataclasses import replace

import pytest
from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    Property,
)
from app.models.work_subject import WorkSubject
from app.services.living_time_relationship import LivingTimeRelationshipService
from app.services.property_manager import property_manager
from app.services.transit_duration import LivingTimeResult
from app.stores.runtime import living_time_relationship_store, work_subject_store
from tests.ids import uuid_for


class RouteEvidence:
    def __init__(self, result: LivingTimeResult | None) -> None:
        self.result = result
        self.calls: list[dict] = []

    def calculate_living_time(self, **kwargs) -> LivingTimeResult | None:
        self.calls.append(kwargs)
        return self.result


def grounded_residence(conversation_id: str, title: str = "西山庭院") -> Property:
    return property_manager.create(
        conversation_id,
        Property(
            title=title,
            geographic_identity=f"北京市海淀区{title}",
            geographic_precision=GeographicPrecision.COMMUNITY,
            geographic_status=GeographicStatus.GROUNDED,
            lng=116.286,
            lat=40.021,
        ),
    )


def grounded_work_subject() -> WorkSubject:
    return WorkSubject(
        identity="融科资讯中心",
        geographic_identity="北京市海淀区融科资讯中心",
        geographic_precision="PLACE",
        geographic_status="GROUNDED",
        lng=116.326178,
        lat=39.984098,
    )


def test_grounded_route_creates_authoritative_living_time_and_meaning() -> None:
    conversation_id = uuid_for("grounded-living-time")
    residence = grounded_residence(conversation_id)
    subject = work_subject_store.save(conversation_id, grounded_work_subject())
    route = RouteEvidence(LivingTimeResult(
        27,
        CommuteMode.PUBLIC_TRANSIT,
        evidence_source="AMAP_DIRECTION_API",
        evidence_reference="https://restapi.amap.com/v5/direction/transit/integrated",
    ))
    service = LivingTimeRelationshipService(
        relationships=living_time_relationship_store,
        transit=route,
    )

    admitted = service.establish(
        conversation_id=conversation_id,
        residence=residence,
        work_subject=subject,
        api_key="test-key",
        commute_requirement_minutes=30,
    )

    assert admitted is not None
    relationship = admitted.relationship
    assert relationship.residence_property_id == residence.id
    assert relationship.residence_identity == "西山庭院"
    assert relationship.residence_geographic_identity == "北京市海淀区西山庭院"
    assert relationship.work_subject_identity == "融科资讯中心"
    assert relationship.work_geographic_identity == "北京市海淀区融科资讯中心"
    assert relationship.travel_minutes == 27
    assert relationship.travel_mode == CommuteMode.PUBLIC_TRANSIT
    assert relationship.evidence_source == "AMAP_DIRECTION_API"
    assert "amap.com/v5/direction/transit" in relationship.evidence_reference
    assert admitted.requirement is not None
    assert admitted.requirement.maximum_minutes == 30
    assert admitted.requirement.satisfied is True
    assert living_time_relationship_store.get(
        conversation_id, residence.id or "",
    ) == relationship

    # Existing Property commute projection remains available to its caller.
    updated = property_manager.update_commute_minutes(
        residence.id or "",
        conversation_id,
        relationship.travel_minutes,
        relationship.travel_mode,
    )
    assert updated is not None
    assert (updated.commute_minutes, updated.commute_mode) == (
        27, CommuteMode.PUBLIC_TRANSIT,
    )


def test_requirement_is_personal_meaning_not_living_time_reality() -> None:
    conversation_id = uuid_for("living-time-requirement-meaning")
    residence = grounded_residence(conversation_id)
    subject = work_subject_store.save(conversation_id, grounded_work_subject())
    service = LivingTimeRelationshipService(
        relationships=living_time_relationship_store,
        transit=RouteEvidence(LivingTimeResult(
            34,
            CommuteMode.PUBLIC_TRANSIT,
            evidence_source="AMAP_DIRECTION_API",
            evidence_reference="amap://route-evidence",
        )),
    )

    admitted = service.establish(
        conversation_id=conversation_id,
        residence=residence,
        work_subject=subject,
        api_key="test-key",
        commute_requirement_minutes=30,
    )

    assert admitted is not None and admitted.requirement is not None
    assert admitted.relationship.travel_minutes == 34
    assert admitted.requirement.satisfied is False
    assert not hasattr(admitted.relationship, "maximum_minutes")


@pytest.mark.parametrize("missing", ["residence", "work", "route", "evidence"])
def test_missing_grounded_endpoint_or_route_evidence_creates_no_relationship(
    missing: str,
) -> None:
    conversation_id = uuid_for(f"living-time-missing-{missing}")
    residence = grounded_residence(conversation_id)
    subject = work_subject_store.save(conversation_id, grounded_work_subject())
    if missing == "residence":
        residence = replace(residence, geographic_status=GeographicStatus.UNRESOLVED)
    if missing == "work":
        subject = replace(subject, geographic_status="UNRESOLVED")  # type: ignore[arg-type]
    result = LivingTimeResult(
        27,
        CommuteMode.PUBLIC_TRANSIT,
        evidence_source=(None if missing == "evidence" else "AMAP_DIRECTION_API"),
        evidence_reference=(None if missing == "evidence" else "amap://route-evidence"),
    )
    route = RouteEvidence(None if missing == "route" else result)
    service = LivingTimeRelationshipService(
        relationships=living_time_relationship_store,
        transit=route,
    )

    assert service.establish(
        conversation_id=conversation_id,
        residence=residence,
        work_subject=subject,
        api_key="test-key",
        commute_requirement_minutes=30,
    ) is None
    assert living_time_relationship_store.get(
        conversation_id, residence.id or "",
    ) is None
