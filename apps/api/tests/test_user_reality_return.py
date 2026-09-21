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
            assert "融科·昆仑巢" in prompt or "另一住所" in prompt
            if "该住所室内噪音水平如何？" in prompt:
                quote = "晚上去看了，关窗以后还是能明显听到路上的车声。"
                answered = quote in prompt
                return json.dumps({
                    "unknown_reference": "该住所室内噪音水平如何？",
                    "reality_type": "INDOOR_SOUND_OBSERVATION" if answered else "NONE",
                    "value": quote if answered else None,
                }, ensure_ascii=False)
            assert "该住所内是否有日常使用的独立厨房？" in prompt
            answered = "我问了，有独立厨房。" in prompt
            return json.dumps({
                "unknown_reference": "该住所内是否有日常使用的独立厨房？",
                "reality_type": "INDEPENDENT_KITCHEN" if answered else "NONE",
                "value": True if answered else None,
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

    property_manager.update_meaningful_unknown(
        home.id, conversation_id,
        question="该住所室内噪音水平如何？",
        why="影响居住判断", state_hash="unknown-noise",
    )
    property_manager.update_reality_action(
        home.id, conversation_id,
        action_type="USER_REALITY", label="实地在室内不同时段感受噪音",
        why="需要亲自观察", state_hash="action-noise",
    )
    unrelated = user_reality_return.admit(
        conversation_id, home.id, "我今天去了超市。",
    )
    assert unrelated is None
    assert property_manager.get_scoped(home.id, conversation_id).indoor_sound_observation is None

    expression = "我晚上去看了，关窗以后还是能明显听到路上的车声。"
    observed = client.post("/api/chat/stream", json={
        "conversation_id": conversation_id,
        "message": expression,
        "user_reality_property_id": home.id,
    })
    assert observed.status_code == 200
    assert "world-consequence-ready" in observed.text
    restored = property_manager.get_scoped(home.id, conversation_id)
    assert restored.indoor_sound_observation == "晚上去看了，关窗以后还是能明显听到路上的车声。"
    assert restored.indoor_sound_observation_source == "USER_PROVIDED"
    assert restored.indoor_sound_observation_unknown == "该住所室内噪音水平如何？"
    assert restored.meaningful_unknown is None
    assert restored.reality_action_type is None
    assert restored.feedback_move_type is None
    assert "dB" not in restored.indoor_sound_observation
    assert "严重" not in restored.indoor_sound_observation
    persisted = client.get(f"/api/properties?conversation_id={conversation_id}").json()
    assert next(p for p in persisted["items"] if p["id"] == home.id)["indoor_sound_observation"] == restored.indoor_sound_observation

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
    unrelated_kitchen = user_reality_return.admit(conversation_id, other.id, "今天天气不错。")
    assert unrelated_kitchen is None
    assert property_manager.get_scoped(other.id, conversation_id).independent_kitchen is None
