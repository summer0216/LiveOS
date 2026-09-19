import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
    PropertyRentSource,
)
from app.services.chat_service import chat_service
from app.services.property_manager import property_manager
from app.services.property_reality_service import property_reality_service
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation

client = TestClient(app)


def test_focused_rent_answer_is_scoped_durable_and_exposed_before_reply(monkeypatch):
    cid = uuid_for("focused-rent-answer")
    other_cid = uuid_for("focused-rent-answer-other")
    create_owned_conversation(client, cid)
    create_owned_conversation(client, other_cid)
    target = create_candidate(cid, "目标住宅")
    untouched = create_candidate(cid, "其他住宅")
    foreign = create_candidate(other_cid, "目标住宅")
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *args: iter(["reply"]))
    monkeypatch.setattr(chat_service, "_update_profile", lambda *a, **k: pytest.fail("Rent must not mutate Profile"))
    response = client.post("/api/chat/stream", json={
        "conversation_id": cid, "message": "6800/月", "rent_property_id": target.id,
    })
    assert response.status_code == 200
    assert response.text.index("world-consequence-ready") < response.text.index('"reply"')
    stored = property_manager.get_scoped(target.id, cid)
    assert stored.rent == 6800
    assert stored.rent_source == PropertyRentSource.USER_PROVIDED
    assert (stored.lng, stored.lat, stored.commute_minutes, stored.commute_mode) == (
        target.lng, target.lat, target.commute_minutes, target.commute_mode,
    )
    assert stored.provenance == target.provenance
    assert stored.external_id == target.external_id
    assert property_manager.get_scoped(untouched.id, cid).rent is None
    assert property_reality_service.apply_rent_answer(cid, target.id, "6800/月").status == "IDEMPOTENT"
    assert property_reality_service.apply_rent_answer(cid, foreign.id, "6800/月").status == "UNMATCHED"
    assert property_manager.get_scoped(foreign.id, other_cid).rent is None
    restored = client.get(f"/api/properties?conversation_id={cid}").json()["items"]
    assert next(p for p in restored if p["id"] == target.id)["rent_source"] == "USER_PROVIDED"


@pytest.mark.parametrize("answer", ["不知道", "估计6800/月", "6000到7000", "6800或5800", "-6800/月", "0/月", "预算6800"])
def test_rent_answer_requires_one_explicit_actual_amount(answer):
    assert property_reality_service.apply_rent_answer("unused", "unused", answer).status == "NO_EXPLICIT_RENT"


def test_bare_amount_without_selected_property_does_not_write():
    assert property_reality_service.apply_explicit_rent("unused", "6800/月").status == "NO_EXPLICIT_RENT"


def create_candidate(conversation_id: str, title: str) -> Property:
    return property_manager.create(
        conversation_id,
        Property(
            title=title,
            commute_minutes=6,
            commute_mode=CommuteMode.WALKING,
            geographic_identity=f"深圳市南山区{title}",
            geographic_precision=GeographicPrecision.COMMUNITY,
            geographic_status=GeographicStatus.GROUNDED,
            lng=113.946,
            lat=22.544,
            provenance=PropertyProvenance.AMAP_RESIDENTIAL_POI,
            external_id=f"amap-{title}",
        ),
    )


def test_current_user_turn_persists_explicit_rent_reality() -> None:
    conversation_id = uuid_for("property-rent-reality")
    create_owned_conversation(client, conversation_id)
    candidate = create_candidate(conversation_id, "桃李满堂")

    chat_service._prepare_conversation(conversation_id, "桃李满堂租金5800")

    updated = property_manager.get_scoped(candidate.id or "", conversation_id)
    assert updated is not None
    assert updated.rent == 5800
    assert updated.rent_source == PropertyRentSource.USER_CONFIRMED_REALITY
    assert updated.lng == candidate.lng
    assert updated.lat == candidate.lat
    assert updated.commute_minutes == candidate.commute_minutes
    assert updated.commute_mode == candidate.commute_mode
    assert updated.provenance == candidate.provenance
    assert updated.external_id == candidate.external_id


def test_explicit_rent_variants_are_idempotent() -> None:
    conversation_id = uuid_for("property-rent-idempotent")
    create_owned_conversation(client, conversation_id)
    candidate = create_candidate(conversation_id, "桃李满堂")

    first = property_reality_service.apply_explicit_rent(
        conversation_id,
        "桃李满堂房租是5800",
    )
    repeated = property_reality_service.apply_explicit_rent(
        conversation_id,
        "刚确认了，桃李满堂一个月5800",
    )

    assert first.status == "UPDATED"
    assert repeated.status == "IDEMPOTENT"
    assert repeated.property is not None
    assert repeated.property.id == candidate.id
    assert repeated.property.rent == 5800


def test_ambiguous_or_unmatched_property_does_not_mutate_rent() -> None:
    conversation_id = uuid_for("property-rent-ambiguous")
    create_owned_conversation(client, conversation_id)
    broad = create_candidate(conversation_id, "桃李")
    exact = create_candidate(conversation_id, "桃李满堂")

    ambiguous = property_reality_service.apply_explicit_rent(
        conversation_id,
        "桃李满堂租金5800",
    )
    unmatched = property_reality_service.apply_explicit_rent(
        conversation_id,
        "不存在小区租金6200",
    )

    assert ambiguous.status == "AMBIGUOUS"
    assert unmatched.status == "UNMATCHED"
    assert property_manager.get_scoped(broad.id or "", conversation_id).rent is None
    assert property_manager.get_scoped(exact.id or "", conversation_id).rent is None


def test_rent_reality_cannot_update_another_conversation_property() -> None:
    current_conversation = uuid_for("property-rent-current-conversation")
    other_conversation = uuid_for("property-rent-other-conversation")
    create_owned_conversation(client, current_conversation)
    create_owned_conversation(client, other_conversation)
    other = create_candidate(other_conversation, "跨会话小区")

    result = property_reality_service.apply_explicit_rent(
        current_conversation,
        "跨会话小区租金5300",
    )

    assert result.status == "UNMATCHED"
    assert property_manager.get_scoped(other.id or "", other_conversation).rent is None
