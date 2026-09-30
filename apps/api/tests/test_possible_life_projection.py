from app.main import app
from app.models.living_time import LivingTimeRelationship
from app.models.profile_patch import LivingProfilePatch
from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
)
from app.models.work_subject import WorkSubject
from app.services.possible_life_admission import possible_life_admission_service
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.stores.runtime import living_time_relationship_store, work_subject_store
from fastapi.testclient import TestClient
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_authoritative_possible_lives_reach_world_state_with_references() -> None:
    client = TestClient(app)
    conversation_id = uuid_for("possible-life-world-state")
    create_owned_conversation(client, conversation_id)
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

    residence_ids: list[str] = []
    for index, title in enumerate(("西山庭院", "新科祥园")):
        residence = property_manager.create(
            conversation_id,
            Property(
                title=title,
                provenance=PropertyProvenance.AMAP_RESIDENTIAL_POI,
                external_id=f"amap-{index}",
                geographic_identity=f"北京市海淀区{title}",
                geographic_precision=GeographicPrecision.COMMUNITY,
                geographic_status=GeographicStatus.GROUNDED,
                lng=116.286 + index * 0.01,
                lat=39.98,
            ),
        )
        residence_ids.append(residence.id or "")
        living_time_relationship_store.save(
            conversation_id,
            LivingTimeRelationship(
                residence_property_id=residence.id or "",
                residence_identity=title,
                residence_geographic_identity=residence.geographic_identity or "",
                work_subject_identity=subject.identity,
                work_geographic_identity=subject.geographic_identity,
                travel_minutes=20 + index,
                travel_mode=CommuteMode.PUBLIC_TRANSIT,
                evidence_source="AMAP_DIRECTION_API",
                evidence_reference=(
                    "https://restapi.amap.com/v5/direction/transit/integrated"
                ),
            ),
        )
        assert possible_life_admission_service.admit(
            conversation_id, residence.id or "",
        ) is not None

    response = client.get(
        "/api/possible-lives", params={"conversation_id": conversation_id},
    )

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    assert {item["id"] for item in items}.__len__() == 2
    assert {item["residence_property_id"] for item in items} == set(residence_ids)
    for item in items:
        assert item["work_subject"]["identity"] == subject.identity
        assert item["work_subject"]["relationship"] == "WORK"
        assert item["living_time_residence_property_id"] == (
            item["living_time"]["residence_property_id"]
        )
        assert item["living_time"]["evidence_source"] == "AMAP_DIRECTION_API"
        assert item["personal_meaning"] == {
            "reference": "living_profile.commute_minutes",
            "maximum_commute_minutes": 30,
            "satisfied": True,
        }
