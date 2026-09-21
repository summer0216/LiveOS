"""A user can return factual rent Reality without an active Unknown."""

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


def test_unprompted_focused_rent_requires_explicit_fact_and_scoped_home(monkeypatch):
    client = TestClient(app)
    conversation_id = uuid_for("unprompted-focused-rent")
    create_owned_conversation(client, conversation_id)
    home = property_manager.create(conversation_id, Property(
        title="龙湖时代天街", geographic_identity="成都市龙湖时代天街",
        geographic_precision=GeographicPrecision.AREA,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.917856, lat=30.754633,
    ))
    other = property_manager.create(conversation_id, Property(
        title="另一住所", geographic_identity="成都市另一住所",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.92, lat=30.75,
    ))
    assert home.id and other.id

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            if "我希望租金2000" in prompt or "另一住所租金2000" in prompt:
                return json.dumps({
                    "unknown_reference": None, "reality_type": "NONE", "value": None,
                })
            if 'Active Unknown: "有独立厨房吗？"' in prompt:
                return json.dumps({
                    "unknown_reference": "有独立厨房吗？",
                    "reality_type": "INDEPENDENT_KITCHEN", "value": True,
                }, ensure_ascii=False)
            return json.dumps({
                "unknown_reference": None, "reality_type": "RENT", "value": 2000,
            })

    monkeypatch.setattr(user_reality_return, "_intelligence", Intelligence())
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *_args: iter(["ok"]))
    monkeypatch.setattr(living_meaning_service, "form", lambda *_args: None)

    assert user_reality_return.admit(conversation_id, home.id, "我希望租金2000") is None
    assert user_reality_return.admit(conversation_id, home.id, "另一住所租金2000") is None
    assert user_reality_return.admit(conversation_id, "not-a-focused-property", "租金2000") is None
    assert property_manager.get_scoped(home.id, conversation_id).rent is None

    response = client.post("/api/chat/stream", json={
        "conversation_id": conversation_id,
        "message": "租金2000",
        "user_reality_property_id": home.id,
    })
    assert response.status_code == 200
    assert "world-consequence-ready" in response.text
    persisted = client.get(f"/api/properties?conversation_id={conversation_id}")
    by_id = {item["id"]: item for item in persisted.json()["items"]}
    assert by_id[home.id]["rent"] == 2000
    assert by_id[home.id]["rent_source"] == "USER_PROVIDED"
    assert by_id[other.id]["rent"] is None

    property_manager.update_meaningful_unknown(
        other.id, conversation_id, question="有独立厨房吗？",
        why="影响日常使用", state_hash="kitchen-unknown",
    )
    property_manager.update_reality_action(
        other.id, conversation_id, action_type="USER_REALITY",
        label="确认厨房", why="需要核实", state_hash="kitchen-action",
    )
    admitted = user_reality_return.admit(conversation_id, other.id, "我问了，有独立厨房。")
    assert admitted is not None and admitted.independent_kitchen is True
