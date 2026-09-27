import json

from app.main import app
from app.models.decision_geography import DecisionGeography
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus, Property
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_geography_service import decision_geography_service
from app.services.decision_signal_intelligence import decision_signal_intelligence
from app.services.living_meaning_service import living_meaning_service
from app.services.profile_intelligence import profile_intelligence
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.services.user_reality_return import user_reality_return
from fastapi.testclient import TestClient
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_personal_layout_requirement_unknown_match_and_mismatch(monkeypatch):
    client = TestClient(app)
    cid = uuid_for("layout-requirement-continuity")
    create_owned_conversation(client, cid)
    conversation_manager.append_user_message(cid, "我想住龙湖时代天街")
    home = property_manager.create(cid, Property(
        title="龙湖时代天街", geographic_identity="成都市龙湖时代天街",
        geographic_status=GeographicStatus.GROUNDED,
        geographic_precision=GeographicPrecision.PLACE,
        lng=103.920730, lat=30.753792,
    ))
    question = "龙湖时代天街这个住所实际是什么户型？"
    rejected = []
    seen_basis = []

    class ExpressionIntelligence:
        def generate_json(self, prompt, **_kwargs):
            if "Interpret the CURRENT user expression" in prompt:
                message = json.loads(prompt.split("Current message: ", 1)[1].splitlines()[0])
                requirement = message == "预算2000，两室一厅"
                factual = "实际" in message or "这个住所是" in message
                return json.dumps({
                    "claim_nature": "PERSONAL_REQUIREMENT" if requirement else "PROPERTY_REALITY" if factual else "OTHER",
                    "layout_requirement": "两室一厅" if requirement else None,
                    "reality_type": "LAYOUT" if factual else None,
                    "claim_quote": "一室一厅" if "一室一厅" in message else "两室一厅" if factual else None,
                    "property_id": home.id if factual else None,
                    "binding_evidence": "龙湖时代天街" if factual else None,
                    "binding_source": "USER_EXPRESSION" if factual else None,
                    "attention_property_id": home.id if requirement else None,
                    "attention_evidence": "我想住龙湖时代天街" if requirement else None,
                }, ensure_ascii=False)
            message = json.loads(prompt.split("Current user message: ", 1)[1].splitlines()[0])
            return json.dumps({
                "unknown_reference": None, "reality_type": "LAYOUT",
                "value": "一室一厅" if "一室一厅" in message else "两室一厅",
            }, ensure_ascii=False)

    class MeaningIntelligence:
        def generate_json(self, prompt, **_kwargs):
            basis, _ = json.JSONDecoder().raw_decode(prompt.split("Grounded Reality:", 1)[1].lstrip())
            seen_basis.append(basis)
            actual = basis.get("LAYOUT_REALITY")
            mismatch = actual == "一室一厅"
            meaning = (
                "实际一室一厅与所需两室一厅不一致，未满足户型要求。" if mismatch else
                "实际户型符合两室一厅的明确要求，其他个人适配性仍未知。" if actual else
                "期望两室一厅，实际户型未知，暂不能判断是否满足户型要求。"
            )
            judgment = (
                "已知户型不符合明确要求，其他条件仍需独立判断。" if mismatch else
                "已满足已声明的户型条件，尚不能据此判断整体适合。" if actual else
                "户型要求已明确，住所实际户型仍待确认。"
            )
            facts = [
                {"fact": key, "value": basis[key]}
                for key in ("HOME_IDENTITY", "LAYOUT_REQUIREMENT")
            ]
            if actual:
                facts.append({"fact": "LAYOUT_REALITY", "value": actual})
            if "Audit whether EVERY claim" in prompt:
                proposed = json.loads(prompt.split("Proposed interpretation: ", 1)[1].splitlines()[0])
                unsupported = mismatch and proposed == "已经满足户型要求。"
                if unsupported:
                    rejected.append(proposed)
                return json.dumps({"supported": not unsupported,
                                   "unsupported_claims": [proposed] if unsupported else []})
            if "Choose ONE reliable next action" in prompt:
                return json.dumps({"action_type": "USER_REALITY", "action_label": "核实住所实际户型",
                                   "why_this_action": "实际户型需直接确认", "unknown_reference": question})
            if "Judge whether this proposed Unknown deserves" in prompt:
                return json.dumps({
                    "question_reference": question, "judgment_reference": judgment,
                    "current_reality_sufficient": False, "material_decision_change": True,
                    "single_observable_fact": True, "impact_without_unsupported_bridge": True,
                    "sufficient_dimension": "", "plausible_answer_a": "两室一厅",
                    "impact_a": "满足明确户型条件", "plausible_answer_b": "一室一厅",
                    "impact_b": "不满足明确户型条件", "reason": "实际户型决定是否符合所需布局",
                })
            if "Identify the ONE unknown Reality" in prompt:
                assert actual is None
                return json.dumps({
                    "unknown_fact": "ACTUAL_LAYOUT", "question": question,
                    "why_it_matters": "实际户型决定能否满足用户明确的户型要求",
                    "meaning_reference": meaning, "judgment_reference": judgment, "grounding": facts,
                })
            if "Judge whether the CURRENT Possible Life" in prompt:
                return json.dumps({
                    "status": "DECISION_READY" if actual else "NEED_MORE_REALITY",
                    "reason": "户型条件的符合情况已明确" if actual else "实际户型尚未知",
                    "meaning_reference": meaning, "judgment_reference": judgment, "grounding": facts,
                })
            if "Form one provisional Current Judgment" in prompt:
                return json.dumps({
                    "judgment": "已经满足户型要求。" if mismatch and "previous answer was rejected" not in prompt else judgment,
                    "meaning_reference": meaning, "grounding": facts,
                })
            return json.dumps({
                "meaning": "已经满足户型要求。" if mismatch and "previous answer was rejected" not in prompt else meaning,
                "grounding": facts,
            })

    monkeypatch.setattr(user_reality_return, "_intelligence", ExpressionIntelligence())
    monkeypatch.setattr(living_meaning_service, "_intelligence", MeaningIntelligence())
    monkeypatch.setattr(profile_intelligence, "analyze", lambda history, *_args, **_kwargs:
                        ProfileAnalysis(patch=LivingProfilePatch(
                            budget=2000 if history[-1].content == "预算2000，两室一厅" else None,
                        )))
    monkeypatch.setattr(decision_signal_intelligence, "analyze", lambda *_args: DecisionGeography())
    monkeypatch.setattr(decision_geography_service, "apply", lambda *args, **kwargs: None)
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *args: iter(["reply"]))

    def submit(message):
        response = client.post("/api/chat/stream", json={"conversation_id": cid, "message": message})
        assert response.status_code == 200 and "event: error" not in response.text
        assert "world-consequence-ready" in response.text
        if message == "预算2000，两室一厅":
            assert f'"focus_property_id": "{home.id}"' in response.text
        return client.get(f"/api/properties?conversation_id={cid}").json()["items"][0]

    unknown = submit("预算2000，两室一厅")
    profile = client.get(f"/api/profiles/{cid}").json()
    assert profile["budget"] == 2000 and profile["layout_requirement"] == "两室一厅"
    assert unknown["layout_expression"] is None and unknown["rent"] is None
    assert unknown["decision_readiness"] == "NEED_MORE_REALITY"
    assert unknown["meaningful_unknown"] == question
    assert unknown["reality_action_type"] == "USER_REALITY"
    old_hash = property_manager.get_scoped(home.id, cid).living_meaning_reality_hash
    assert any(basis.get("LAYOUT_REQUIREMENT") == "两室一厅" and "LAYOUT_REALITY" not in basis for basis in seen_basis)

    submit("谢谢")
    assert profile_manager.get(cid).layout_requirement == "两室一厅"
    matched = submit("龙湖时代天街这个住所是两室一厅")
    matched_home = property_manager.get_scoped(home.id, cid)
    assert matched["layout_expression"] == "两室一厅" and matched["layout_source"] == "USER_PROVIDED"
    assert matched["meaningful_unknown"] is None
    assert matched_home.living_meaning_reality_hash != old_hash
    basis = living_meaning_service._basis(matched_home, profile_manager.get(cid))
    assert "LAYOUT_REALITY ↔ LAYOUT_REQUIREMENT" in living_meaning_service._personal_reality_connections(basis)

    mismatched = submit("龙湖时代天街实际是一室一厅")
    assert mismatched["layout_expression"] == "一室一厅"
    assert profile_manager.get(cid).layout_requirement == "两室一厅"
    assert mismatched["living_meaning"] != matched["living_meaning"]
    assert mismatched["current_judgment"] != matched["current_judgment"]
    assert mismatched["living_meaning"] != "已经满足户型要求。"
    assert mismatched["current_judgment"] != "已经满足户型要求。"
    assert len(rejected) == 2
    assert mismatched["rent"] is None and profile_manager.get(cid).budget == 2000
