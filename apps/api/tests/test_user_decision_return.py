"""One focused regression for user-owned Decision State."""

import json

from fastapi.testclient import TestClient

from app.main import app
from app.models.property import GeographicStatus, Property
from app.services.chat_service import WORLD_CONSEQUENCE_READY, chat_service
from app.services.property_manager import property_manager
from app.services.user_decision_return import user_decision_return
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_focused_user_decision_is_explicit_scoped_and_durable(monkeypatch):
    client = TestClient(app)
    conversation_id = uuid_for("user-decision-ready")
    other_conversation_id = uuid_for("user-decision-other")
    create_owned_conversation(client, conversation_id)
    create_owned_conversation(client, other_conversation_id)
    home = property_manager.create(conversation_id, Property(
        title="融科·昆仑巢", geographic_status=GeographicStatus.GROUNDED,
        geographic_identity="北京市融科·昆仑巢", lng=116.321, lat=39.981,
    ))
    other = property_manager.create(conversation_id, Property(
        title="另一处真实住所", geographic_status=GeographicStatus.GROUNDED,
        geographic_identity="北京市另一处真实住所", lng=116.322, lat=39.982,
    ))
    assert home.id and other.id
    property_manager.update_living_meaning(
        home.id, conversation_id, meaning="通勤便利，但成本有压力。",
        reality_hash="reality-1",
    )
    property_manager.update_current_judgment(
        home.id, conversation_id, judgment="短通勤与成本压力并存。",
        state_hash="judgment-1",
    )
    property_manager.update_decision_readiness(
        home.id, conversation_id, status="DECISION_READY",
        reason="现有现实足以判断", state_hash="readiness-1",
        judgment_hash="judgment-1",
    )

    class Intelligence:
        stance = "NONE"

        def generate_json(self, prompt, **_kwargs):
            expression = json.loads(prompt.split("Current user expression: ", 1)[1].split("\n", 1)[0])
            return json.dumps({"stance": self.stance, "user_expression": expression})

    intelligence = Intelligence()
    monkeypatch.setattr(user_decision_return, "_intelligence", intelligence)
    ambiguous = "这个选择还需要再想想。"
    assert user_decision_return.admit(conversation_id, home.id, ambiguous) is None
    assert property_manager.get_scoped(home.id, conversation_id).user_decision_expression is None

    intelligence.stance = "ACCEPT"
    expression = "虽然贵300，但是通勤太方便了，我愿意接受这个取舍。"
    assert user_decision_return.admit(other_conversation_id, home.id, expression) is None
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *_args: iter(["ok"]))
    events = list(chat_service.chat_stream(
        conversation_id, expression, user_decision_property_id=home.id,
    ))
    assert WORLD_CONSEQUENCE_READY in events
    stored = property_manager.get_scoped(home.id, conversation_id)
    assert stored.user_decision_expression == expression
    assert stored.user_decision_stance == "ACCEPT"
    assert stored.user_decision_source == "USER_PROVIDED"
    assert stored.living_meaning == "通勤便利，但成本有压力。"
    assert stored.current_judgment == "短通勤与成本压力并存。"
    assert stored.decision_readiness == "DECISION_READY"
    assert stored.rent is None
    assert property_manager.get_scoped(other.id, conversation_id).user_decision_expression is None
    assert user_decision_return.admit(conversation_id, home.id, expression) is None
    restored = client.get(f"/api/properties?conversation_id={conversation_id}")
    assert restored.status_code == 200
    by_id = {item["id"]: item for item in restored.json()["items"]}
    assert by_id[home.id]["user_decision_expression"] == expression
    assert by_id[other.id]["user_decision_expression"] is None
