import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.ai_client import ai_client
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.schemas.decision import DecisionResult
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from tests.ids import uuid_for

CONVERSATION_IDS = (
    uuid_for("record-waiting"),
    uuid_for("record-ready"),
    uuid_for("record-repeated"),
    uuid_for("record-save-failure"),
    uuid_for("record-isolation-a"),
    uuid_for("record-isolation-b"),
    uuid_for("record-snapshot"),
    uuid_for("record-concurrent"),
)


@pytest.fixture(autouse=True)
def clean_record_data() -> Iterator[None]:
    for conversation_id in CONVERSATION_IDS:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)

    yield

    for conversation_id in CONVERSATION_IDS:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)


def create_profile(
    conversation_id: str,
    *,
    budget: int = 6000,
) -> None:
    profile_manager.merge(
        conversation_id=conversation_id,
        patch=LivingProfilePatch(
            work_location="南山科技园",
            budget=budget,
            commute_minutes=30,
            preferred_city="深圳",
            family_size=2,
            has_pet=False,
        ),
        latest_insights=[],
    )


def create_property(
    conversation_id: str,
    title: str,
) -> Property:
    return property_manager.create(
        conversation_id=conversation_id,
        property_=Property(
            title=title,
            district="南山",
            rent=5800,
            area=65,
            bedrooms=2,
            bathrooms=1,
            commute_minutes=25,
            pet_friendly=True,
        ),
    )


def ready_json(property_id: str) -> str:
    return json.dumps(
        {
            "status": "ready",
            "summary": "当前候选房源符合已知的预算与通勤要求。",
            "best_property_id": property_id,
            "reasons": [
                {
                    "title": "预算匹配",
                    "description": "月租处于当前预算范围内。",
                },
            ],
            "trade_offs": [
                {
                    "title": "面积取舍",
                    "description": "面积为当前提供的 65 平方米。",
                },
            ],
            "confidence": 0.82,
        },
        ensure_ascii=False,
    )


def prepare_ready(
    monkeypatch: pytest.MonkeyPatch,
    conversation_id: str,
    title: str,
) -> Property:
    create_profile(conversation_id)
    property_ = create_property(conversation_id, title)
    assert property_.id is not None
    monkeypatch.setattr(
        ai_client,
        "generate_json",
        lambda _prompt: ready_json(property_.id),
    )
    return property_


def test_waiting_decision_is_not_saved() -> None:
    result = decision_service.generate(uuid_for("record-waiting"))

    assert result.status == "waiting"
    assert decision_record_service.list(uuid_for("record-waiting")) == []


def test_ready_decision_saves_one_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("record-ready")
    property_ = prepare_ready(monkeypatch, conversation_id, "Ready 房源")

    result = decision_service.generate(conversation_id)
    records = decision_record_service.list(conversation_id)

    assert result.status == "ready"
    assert len(records) == 1
    assert records[0].id
    assert records[0].conversation_id == conversation_id
    assert records[0].best_property_id == property_.id
    assert records[0].created_at.tzinfo is not None


def test_each_ready_decision_appends_a_new_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("record-repeated")
    prepare_ready(monkeypatch, conversation_id, "重复推荐房源")

    first_result = decision_service.generate(conversation_id)
    second_result = decision_service.generate(conversation_id)
    records = decision_record_service.list(conversation_id)

    assert first_result.status == "ready"
    assert second_result.status == "ready"
    assert len(records) == 2
    assert records[0].id != records[1].id


def test_save_failure_does_not_change_ready_decision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("record-save-failure")
    prepare_ready(monkeypatch, conversation_id, "保存失败房源")

    def fail_save(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("Record store unavailable")

    monkeypatch.setattr(decision_record_service, "save", fail_save)

    result = decision_service.generate(conversation_id)

    assert result.status == "ready"
    assert decision_record_service.list(conversation_id) == []


def test_records_are_shared_by_owner_across_conversations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_a = uuid_for("record-isolation-a")
    conversation_b = uuid_for("record-isolation-b")
    property_a = prepare_ready(monkeypatch, conversation_a, "A 房源")
    decision_service.generate(conversation_a)
    property_b = prepare_ready(monkeypatch, conversation_b, "B 房源")
    decision_service.generate(conversation_b)

    records_a = decision_record_service.list(conversation_a)
    records_b = decision_record_service.list(conversation_b)

    assert len(records_a) == 2
    assert len(records_b) == 2
    assert {record.best_property_id for record in records_a} == {
        property_a.id,
        property_b.id,
    }
    assert records_a == records_b


def test_record_remains_a_snapshot_after_source_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("record-snapshot")
    property_ = prepare_ready(monkeypatch, conversation_id, "快照房源")
    decision_service.generate(conversation_id)
    original_record = decision_record_service.list(conversation_id)[0]
    original_snapshot = original_record.model_dump()

    create_profile(conversation_id, budget=9000)
    property_.title = "修改后的房源"
    property_.rent = 8800

    stored_record = decision_record_service.list(conversation_id)[0]

    assert stored_record.model_dump() == original_snapshot


def test_concurrent_writes_do_not_lose_records() -> None:
    conversation_id = uuid_for("record-concurrent")
    decision = DecisionResult.model_validate_json(
        ready_json(uuid_for("concurrent-property")),
    )

    with ThreadPoolExecutor(max_workers=8) as executor:
        records = list(
            executor.map(
                lambda _index: decision_record_service.save(
                    conversation_id,
                    decision,
                ),
                range(40),
            ),
        )

    stored_records = decision_record_service.list(conversation_id)

    assert len(records) == 40
    assert len(stored_records) == 40
    assert len({record.id for record in stored_records}) == 40
