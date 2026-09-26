import json

from fastapi.testclient import TestClient

from app.main import app
from app.models.profile import LivingProfile
from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyRentSource,
)
from app.services.living_meaning_service import LivingMeaningService
from app.services.property_manager import property_manager
from app.stores.runtime import profile_store
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_readiness_gates_unknown_and_invalidates_with_reality():
    conversation_id = uuid_for("decision-readiness")
    client = TestClient(app)
    create_owned_conversation(client, conversation_id)
    profile_store.save(conversation_id, LivingProfile(
        work_location="融科资讯中心", budget=6000,
        geographic_status=GeographicStatus.GROUNDED,
        geographic_precision=GeographicPrecision.PLACE,
        geographic_identity="北京市融科资讯中心", lng=116.32, lat=39.98,
    ))
    home = property_manager.create(conversation_id, Property(
        title="融科·昆仑巢", rent=6300,
        rent_source=PropertyRentSource.USER_PROVIDED,
        geographic_status=GeographicStatus.GROUNDED,
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_identity="北京市融科·昆仑巢", lng=116.321, lat=39.981,
        commute_minutes=1, commute_mode=CommuteMode.WALKING,
        grocery_external_id="grocery-1", grocery_name="真实超市",
        grocery_identity="北京市真实超市", grocery_lng=116.322,
        grocery_lat=39.982, grocery_walking_minutes=7,
    ))
    assert home.id is not None
    property_manager.update_meaningful_unknown(
        home.id, conversation_id, question="有独立厨房吗？",
        why="影响日常使用", state_hash="kitchen-unknown",
    )
    property_manager.update_reality_action(
        home.id, conversation_id, action_type="USER_REALITY",
        label="核实厨房", why="需要确认", state_hash="kitchen-action",
    )
    property_manager.admit_user_kitchen_reality(
        home.id, conversation_id, unknown_hash="kitchen-unknown",
        kitchen_present=True,
    )
    property_manager.update_meaningful_unknown(
        home.id, conversation_id, question="室内噪音如何？",
        why="影响居住", state_hash="sound-unknown",
    )
    property_manager.update_reality_action(
        home.id, conversation_id, action_type="USER_REALITY",
        label="实地感受", why="需要观察", state_hash="sound-action",
    )
    observation = "晚上去看了，关窗以后还是能明显听到路上的车声。"
    property_manager.admit_user_sound_observation(
        home.id, conversation_id, unknown_hash="sound-unknown",
        unknown_question="室内噪音如何？", observation=observation,
    )
    property_manager.update_meaningful_unknown(
        home.id, conversation_id,
        question="关窗后夜间室内噪音实测是多少分贝？",
        why="补充精确程度", state_hash="old-unknown",
    )
    property_manager.update_reality_action(
        home.id, conversation_id, action_type="USER_REALITY",
        label="测量分贝", why="补充测量", state_hash="old-action",
    )

    meaning = "短通勤便利，但租金超预算且夜间关窗后仍能听到车声。"
    judgment = "这是短通勤便利与超预算、夜间车声并存的居住选择。"
    next_question = "实际起居空间是否足够？"

    class Intelligence:
        def __init__(self):
            self.status = "INVALID"
            self.calls: list[str] = []

        def generate_json(self, prompt, **_kwargs):
            self.calls.append(prompt)
            if "Audit whether EVERY claim" in prompt:
                return json.dumps({"supported": True, "unsupported_claims": []})
            grounding = [
                {"fact": "WORK_COMMUTE", "value": "1min WALKING"},
                {"fact": "GROCERY_WALK", "value": "7min WALKING"},
            ]
            if "Judge whether the CURRENT Possible Life" in prompt:
                return json.dumps({
                    "status": self.status,
                    "reason": "已有通勤、成本和夜间声音 Reality，足以面对目前取舍。",
                    "meaning_reference": meaning,
                    "judgment_reference": judgment,
                    "grounding": grounding,
                }, ensure_ascii=False)
            if "Judge whether this proposed Unknown" in prompt:
                return json.dumps({
                    "question_reference": next_question,
                    "judgment_reference": judgment,
                    "current_reality_sufficient": False,
                    "material_decision_change": True,
                    "single_observable_fact": True,
                    "impact_without_unsupported_bridge": True,
                    "sufficient_dimension": "",
                    "plausible_answer_a": "空间足够",
                    "impact_a": "当前居住取舍保持",
                    "plausible_answer_b": "空间不足",
                    "impact_b": "新增日常居住限制",
                    "reason": "空间是否足够会改变生活判断。",
                }, ensure_ascii=False)
            if "Choose ONE reliable next action" in prompt:
                return json.dumps({
                    "action_type": "USER_REALITY",
                    "action_label": "实地确认起居空间",
                    "why_this_action": "需要直接观察。",
                    "unknown_reference": next_question,
                }, ensure_ascii=False)
            if "Identify the ONE unknown Reality" in prompt:
                return json.dumps({
                    "unknown_fact": "LIVING_SPACE",
                    "question": next_question,
                    "why_it_matters": "空间不足会改变便利与成本的权衡。",
                    "meaning_reference": meaning,
                    "judgment_reference": judgment,
                    "grounding": grounding,
                }, ensure_ascii=False)
            if "Form one provisional Current Judgment" in prompt:
                return json.dumps({
                    "judgment": judgment, "meaning_reference": meaning,
                    "grounding": grounding,
                }, ensure_ascii=False)
            return json.dumps({"meaning": meaning, "grounding": grounding}, ensure_ascii=False)

    intelligence = Intelligence()
    service = LivingMeaningService(intelligence=intelligence)
    basis = service._basis(property_manager.get_scoped(home.id, conversation_id),
                           profile_store.get(conversation_id))
    assert service._generate_decision_readiness(basis, meaning, judgment) is None

    intelligence.status = "DECISION_READY"
    ready = service.form(conversation_id, home.id)
    assert ready.status == "DECISION_READY"
    stored = property_manager.get_scoped(home.id, conversation_id)
    assert stored.decision_readiness == "DECISION_READY"
    assert stored.meaningful_unknown is None
    assert stored.reality_action_type is None
    assert stored.indoor_sound_observation == observation
    assert stored.living_meaning == meaning
    assert stored.current_judgment == judgment
    assert not any("Identify the ONE unknown Reality" in call for call in intelligence.calls)
    api_property = client.get(f"/api/properties?conversation_id={conversation_id}").json()["items"][0]
    assert api_property["decision_readiness"] == "DECISION_READY"
    assert api_property["meaningful_unknown"] is None

    changed = property_manager.update_confirmed_rent(home.id, conversation_id, 6400)
    assert changed.decision_readiness is None
    intelligence.status = "NEED_MORE_REALITY"
    need_more = service.form(conversation_id, home.id)
    assert need_more.status == "UPDATED"
    updated = property_manager.get_scoped(home.id, conversation_id)
    assert updated.decision_readiness == "NEED_MORE_REALITY"
    assert updated.meaningful_unknown == next_question
    assert updated.reality_action_type == "USER_REALITY"
    assert updated.indoor_sound_observation == observation
