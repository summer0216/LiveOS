import json

from fastapi.testclient import TestClient

from app.main import app
from app.models.property import GeographicPrecision, GeographicStatus, Property
from app.services.chat_service import chat_service
from app.services.living_meaning_service import living_meaning_service
from app.services.property_manager import property_manager
from app.services.user_reality_return import user_reality_return
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_focused_user_reality_answer_admits_only_answered_unknown(monkeypatch):
    client = TestClient(app)
    conversation_id = uuid_for("user-reality-return")
    create_owned_conversation(client, conversation_id)
    home = property_manager.create(conversation_id, Property(
        title="融科·昆仑巢",
        geographic_identity="北京市融科·昆仑巢",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.32,
        lat=39.98,
    ))
    property_manager.update_meaningful_unknown(
        home.id, conversation_id,
        question="该住所内是否有日常使用的独立厨房？",
        why="影响日常生活安排", state_hash="unknown-kitchen",
    )
    property_manager.update_reality_action(
        home.id, conversation_id,
        action_type="USER_REALITY", label="向房东或中介核实独立厨房",
        why="需要用户确认", state_hash="action-kitchen",
    )

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            assert "该住所内是否有日常使用的独立厨房？" in prompt
            assert "融科·昆仑巢" in prompt or "另一住所" in prompt
            answered = "我问了，有独立厨房。" in prompt
            return json.dumps({
                "unknown_reference": "该住所内是否有日常使用的独立厨房？",
                "answers_unknown": answered,
                "independent_kitchen": True if answered else None,
            }, ensure_ascii=False)

    monkeypatch.setattr(user_reality_return, "_intelligence", Intelligence())
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *args: iter(["reply"]))
    monkeypatch.setattr(living_meaning_service, "form", lambda *args: None)
    monkeypatch.setattr(chat_service, "_update_profile", lambda *args, **kwargs: None)

    accepted = client.post("/api/chat/stream", json={
        "conversation_id": conversation_id,
        "message": "我问了，有独立厨房。",
        "user_reality_property_id": home.id,
    })
    assert accepted.status_code == 200
    assert "world-consequence-ready" in accepted.text
    stored = property_manager.get_scoped(home.id, conversation_id)
    assert stored.independent_kitchen is True
    assert stored.independent_kitchen_source == "USER_PROVIDED"
    assert stored.meaningful_unknown is None
    assert stored.reality_action_type is None
    assert stored.feedback_move_type is None
    response = client.get(f"/api/properties?conversation_id={conversation_id}").json()
    assert response["items"][0]["independent_kitchen"] is True

    # Another focused property with an active Unknown tests an unrelated answer.
    other = property_manager.create(conversation_id, Property(
        title="另一住所", geographic_identity="北京市另一住所",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.33, lat=39.98,
    ))
    property_manager.update_meaningful_unknown(
        other.id, conversation_id,
        question="该住所内是否有日常使用的独立厨房？",
        why="影响日常生活安排", state_hash="other-unknown",
    )
    property_manager.update_reality_action(
        other.id, conversation_id,
        action_type="USER_REALITY", label="向房东或中介核实独立厨房",
        why="需要用户确认", state_hash="other-action",
    )
    unrelated = user_reality_return.admit(conversation_id, other.id, "今天天气不错。")
    assert unrelated is None
    assert property_manager.get_scoped(other.id, conversation_id).independent_kitchen is None
