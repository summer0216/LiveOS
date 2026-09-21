import json

from fastapi.testclient import TestClient

from app.main import app
from app.models.profile import LivingProfile
from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
)
from app.services.living_meaning_service import LivingMeaningService
from app.services.property_manager import property_manager
from app.stores.runtime import profile_store
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


class FakeMeaningIntelligence:
    def __init__(self) -> None:
        self.include_unsupported_fact = True
        self.recommend_choice = True
        self.return_known_fact_as_unknown = True
        self.use_unsupported_future_causality = True
        self.action_type = "UNSUPPORTED"

    def generate_json(self, prompt: str, **_kwargs) -> str:
        assert "中关村东大院" in prompt
        grounding = [
            {"fact": "WORK_COMMUTE", "value": "1min WALKING"},
            {"fact": "GROCERY_WALK", "value": "7min WALKING"},
        ]
        if "Choose ONE reliable next action" in prompt:
            return json.dumps({
                "action_type": self.action_type,
                "action_label": "现场确认实际居住空间",
                "why_this_action": "这一现实需要直接观察，公开信息不足以确认。",
                "unknown_reference": "实际居住空间是否足够？",
            }, ensure_ascii=False)
        if "unknown Reality" in prompt:
            return json.dumps({
                "unknown_fact": (
                    "WORK_COMMUTE"
                    if self.return_known_fact_as_unknown
                    else "ACTUAL_LIVING_SPACE"
                ),
                "question": (
                    "实际通勤时间是多少？"
                    if self.return_known_fact_as_unknown
                    else "实际居住空间是否足够？"
                ),
                "why_it_matters": (
                    "若租约较短，超预算压力可能很快重新协商或结束。"
                    if self.use_unsupported_future_causality
                    else "实际空间是否满足居住需要，会直接改变便利与成本压力的权衡。"
                ),
                "meaning_reference": "工作和日常采购几乎都可步行解决，但住房成本会带来预算压力。",
                "judgment_reference": "这是用更高住房成本换取极短通勤与日常便利的生活选择。",
                "grounding": grounding,
            }, ensure_ascii=False)
        if "Current Judgment" in prompt:
            return json.dumps({
                "judgment": (
                    "这是最适合用户的选择。"
                    if self.recommend_choice
                    else "这是用更高住房成本换取极短通勤与日常便利的生活选择。"
                ),
                "meaning_reference": "工作和日常采购几乎都可步行解决，但住房成本会带来预算压力。",
                "grounding": grounding,
            }, ensure_ascii=False)
        if self.include_unsupported_fact:
            grounding.append({"fact": "CAFE_WALK", "value": "2min WALKING"})
        return json.dumps({
            "meaning": "工作和日常采购几乎都可步行解决，但住房成本会带来预算压力。",
            "grounding": grounding,
        }, ensure_ascii=False)


def test_grounded_reality_forms_only_supported_persisted_living_meaning():
    client = TestClient(app)
    conversation_id = uuid_for("living-meaning")
    create_owned_conversation(client, conversation_id)
    profile_store.save(conversation_id, LivingProfile(
        work_location="融科资讯中心",
        budget=6000,
        geographic_identity="北京市海淀区融科资讯中心",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.3205,
        lat=39.9839,
    ))
    home = property_manager.create(conversation_id, Property(
        title="中关村东大院",
        geographic_identity="北京市海淀区中关村东大院",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.321,
        lat=39.984,
        commute_minutes=1,
        commute_mode=CommuteMode.WALKING,
        grocery_external_id="amap-grocery-1",
        grocery_name="真实生活超市",
        grocery_identity="北京市海淀区真实生活超市",
        grocery_lng=116.322,
        grocery_lat=39.985,
        grocery_walking_minutes=7,
        provenance=PropertyProvenance.AMAP_RESIDENTIAL_POI,
        external_id="amap-home-1",
    ))
    intelligence = FakeMeaningIntelligence()
    service = LivingMeaningService(intelligence=intelligence)

    rejected = service.form(conversation_id, home.id or "")
    assert rejected.status == "INVALID_MEANING"
    assert property_manager.get_scoped(home.id or "", conversation_id).living_meaning is None

    intelligence.include_unsupported_fact = False
    rejected_judgment = service.form(conversation_id, home.id or "")
    assert rejected_judgment.status == "INVALID_JUDGMENT"
    partial = property_manager.get_scoped(home.id or "", conversation_id)
    assert partial is not None
    assert partial.living_meaning is not None
    assert partial.current_judgment is None

    intelligence.recommend_choice = False
    rejected_unknown = service.form(conversation_id, home.id or "")
    assert rejected_unknown.status == "INVALID_UNKNOWN"
    with_judgment = property_manager.get_scoped(home.id or "", conversation_id)
    assert with_judgment is not None
    assert with_judgment.current_judgment is not None
    assert with_judgment.meaningful_unknown is None

    intelligence.return_known_fact_as_unknown = False
    rejected_future_assumption = service.form(conversation_id, home.id or "")
    assert rejected_future_assumption.status == "INVALID_UNKNOWN"

    intelligence.use_unsupported_future_causality = False
    rejected_action = service.form(conversation_id, home.id or "")
    assert rejected_action.status == "INVALID_ACTION"
    without_action = property_manager.get_scoped(home.id or "", conversation_id)
    assert without_action is not None
    assert without_action.reality_action_type is None

    intelligence.action_type = "USER_REALITY"
    accepted = service.form(conversation_id, home.id or "")
    assert accepted.status == "UPDATED"
    restored = property_manager.get_scoped(home.id or "", conversation_id)
    assert restored is not None
    assert restored.living_meaning is not None
    assert "步行解决" in restored.living_meaning
    assert "预算压力" in restored.living_meaning
    assert "1分钟" not in restored.living_meaning
    assert restored.current_judgment is not None
    assert "生活选择" in restored.current_judgment
    assert "最适合" not in restored.current_judgment
    assert restored.meaningful_unknown == "实际居住空间是否足够？"
    assert restored.meaningful_unknown_why is not None
    assert "权衡" in restored.meaningful_unknown_why
    assert restored.reality_action_type == "USER_REALITY"
    assert restored.reality_action_label == "现场确认实际居住空间"
    assert restored.reality_action_why is not None
    assert restored.rent is None
    assert restored.commute_minutes == 1
    assert restored.grocery_walking_minutes == 7

    changed = property_manager.update_meaningful_unknown(
        home.id or "", conversation_id,
        question="实际室内噪音水平如何？",
        why="噪音可能改变当前权衡。",
        state_hash="changed-unknown",
    )
    assert changed is not None
    assert changed.reality_action_type is None
    assert changed.reality_action_label is None
