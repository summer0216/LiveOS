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

    def generate_json(self, prompt: str, **_kwargs) -> str:
        assert "中关村东大院" in prompt
        grounding = [
            {"fact": "WORK_COMMUTE", "value": "1min WALKING"},
            {"fact": "GROCERY_WALK", "value": "7min WALKING"},
        ]
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
    assert restored.commute_minutes == 1
    assert restored.grocery_walking_minutes == 7
