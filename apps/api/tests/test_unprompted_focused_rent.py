"""A user can return factual rent Reality without an active Unknown."""

import json

from fastapi.testclient import TestClient

from app.main import app
from app.models.profile import LivingProfile
from app.models.property import GeographicPrecision, GeographicStatus, Property
from app.services.chat_service import chat_service
from app.services.living_meaning_service import living_meaning_service
from app.services.property_manager import property_manager
from app.services.user_reality_return import user_reality_return
from app.stores.runtime import profile_store
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_unprompted_focused_rent_requires_explicit_fact_and_scoped_home(monkeypatch):
    client = TestClient(app)
    conversation_id = uuid_for("unprompted-focused-rent")
    create_owned_conversation(client, conversation_id)
    profile_store.save(conversation_id, LivingProfile(budget=2000))
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
        def __init__(self):
            self.meaning_prompts: list[str] = []

        def generate_json(self, prompt, **_kwargs):
            if "Determine whether the USER explicitly established a housing budget" in prompt:
                return json.dumps({"budget": None, "evidence": None})
            if "Interpret what one grounded Possible Life means" in prompt:
                self.meaning_prompts.append(prompt)
                rent = 2100 if "2100 CNY/month" in prompt else 2000
                return json.dumps({
                    "meaning": f"月租{rent}元已明确，但缺少预算等个人约束，当前无法判断住房成本压力。",
                    "grounding": [
                        {"fact": "HOME_IDENTITY", "value": "龙湖时代天街"},
                        {"fact": "RENT_REALITY", "value": f"{rent} CNY/month"},
                    ],
                }, ensure_ascii=False)
            if "Form one provisional Current Judgment" in prompt:
                rent = 2100 if "2100 CNY/month" in prompt else 2000
                return json.dumps({
                    "judgment": f"当前仅明确月租{rent}元，仍需个人约束才能形成更具体的居住判断。",
                    "meaning_reference": f"月租{rent}元已明确，但缺少预算等个人约束，当前无法判断住房成本压力。",
                    "grounding": [
                        {"fact": "HOME_IDENTITY", "value": "龙湖时代天街"},
                        {"fact": "RENT_REALITY", "value": f"{rent} CNY/month"},
                    ],
                }, ensure_ascii=False)
            if "Audit whether EVERY claim" in prompt:
                return json.dumps({"supported": True, "unsupported_claims": []})
            if "Judge whether the CURRENT Possible Life" in prompt:
                rent = 2100 if "2100 CNY/month" in prompt else 2000
                return json.dumps({
                    "status": "NEED_MORE_REALITY",
                    "reason": "缺少预算等个人约束，当前只能确认月租事实。",
                    "meaning_reference": f"月租{rent}元已明确，但缺少预算等个人约束，当前无法判断住房成本压力。",
                    "judgment_reference": f"当前仅明确月租{rent}元，仍需个人约束才能形成更具体的居住判断。",
                    "grounding": [
                        {"fact": "HOME_IDENTITY", "value": "龙湖时代天街"},
                        {"fact": "RENT_REALITY", "value": f"{rent} CNY/month"},
                    ],
                }, ensure_ascii=False)
            if "我希望租金2000" in prompt or "另一住所租金2000" in prompt:
                return json.dumps({
                    "unknown_reference": None, "reality_type": "NONE", "value": None,
                })
            if 'Active Unknown: "有独立厨房吗？"' in prompt:
                return json.dumps({
                    "unknown_reference": "有独立厨房吗？",
                    "reality_type": "INDEPENDENT_KITCHEN", "value": True,
                }, ensure_ascii=False)
            rent = 2100 if "2100" in prompt else 2000
            return json.dumps({
                "unknown_reference": None, "reality_type": "RENT", "value": rent,
            })

    intelligence = Intelligence()
    monkeypatch.setattr(user_reality_return, "_intelligence", intelligence)
    monkeypatch.setattr(living_meaning_service, "_intelligence", intelligence)
    monkeypatch.setattr("app.services.profile_intelligence.ai_client", intelligence)
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *_args: iter(["ok"]))

    assert user_reality_return.admit(conversation_id, home.id, "我希望租金2000") is None
    assert user_reality_return.admit(conversation_id, home.id, "另一住所租金2000") is None
    assert user_reality_return.admit(conversation_id, "not-a-focused-property", "租金2000") is None
    assert property_manager.get_scoped(home.id, conversation_id).rent is None

    property_manager.update_living_meaning(
        home.id, conversation_id,
        meaning="旧的生活含义", reality_hash="stale-reality",
    )
    property_manager.update_current_judgment(
        home.id, conversation_id,
        judgment="旧的当前判断", state_hash="stale-judgment",
    )
    response = client.post("/api/chat/stream", json={
        "conversation_id": conversation_id,
        "message": "龙湖时代天街四栋，月租2000，两室一厅",
        "user_reality_property_id": home.id,
    })
    assert response.status_code == 200
    assert response.text.count("world-consequence-ready") >= 2
    persisted = client.get(f"/api/properties?conversation_id={conversation_id}")
    by_id = {item["id"]: item for item in persisted.json()["items"]}
    assert by_id[home.id]["rent"] == 2000
    assert by_id[home.id]["rent_source"] == "USER_PROVIDED"
    assert by_id[home.id]["bedrooms"] is None
    assert by_id[home.id]["living_meaning"] == (
        "月租2000元已明确，但缺少预算等个人约束，当前无法判断住房成本压力。"
    )
    assert by_id[home.id]["current_judgment"] == (
        "当前仅明确月租2000元，仍需个人约束才能形成更具体的居住判断。"
    )
    assert intelligence.meaning_prompts
    assert "2000 CNY/month" in intelligence.meaning_prompts[0]
    assert by_id[other.id]["rent"] is None

    updated = client.post("/api/chat/stream", json={
        "conversation_id": conversation_id,
        "message": "我确认了一下，月租是2100。",
        "user_reality_property_id": home.id,
    })
    assert updated.status_code == 200
    assert updated.text.count("world-consequence-ready") >= 2
    current = property_manager.get_scoped(home.id, conversation_id)
    assert current is not None
    assert current.rent == 2100
    assert profile_store.get(conversation_id).budget is None
    assert "2100 CNY/month" in intelligence.meaning_prompts[-1]
    assert "2000 CNY/month" not in intelligence.meaning_prompts[-1]
    assert "BUDGET_REALITY" not in intelligence.meaning_prompts[-1]
    assert "no user budget" in intelligence.meaning_prompts[-1]

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
