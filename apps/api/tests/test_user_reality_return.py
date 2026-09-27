import json

from app.main import app
from app.models.decision_geography import DecisionGeography
from app.models.profile import LivingProfile
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus, Property
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_geography_service import decision_geography_service
from app.services.decision_signal_intelligence import decision_signal_intelligence
from app.services.living_meaning_service import living_meaning_service
from app.services.profile_intelligence import BudgetRealityAudit, profile_intelligence
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.services.user_reality_return import user_reality_return
from app.stores.runtime import profile_store
from fastapi.testclient import TestClient
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_expression_context_resolution_precedes_property_admission(monkeypatch):
    client = TestClient(app)
    requirement_cid = uuid_for("expression-requirement")
    explicit_cid = uuid_for("expression-explicit-property")
    continuity_cid = uuid_for("expression-continuity")
    ambiguous_cid = uuid_for("expression-ambiguous")
    focused_cid = uuid_for("expression-focused")
    ids = (requirement_cid, explicit_cid, continuity_cid, ambiguous_cid, focused_cid)
    homes = {}
    for cid in ids:
        create_owned_conversation(client, cid)
        profile_store.save(cid, LivingProfile())
        homes[cid] = property_manager.create(cid, Property(
            title="龙湖时代天街", geographic_identity="成都市龙湖时代天街",
            geographic_precision=GeographicPrecision.PLACE,
            geographic_status=GeographicStatus.GROUNDED,
            lng=103.920730, lat=30.753792,
        ))
    for cid in (requirement_cid, continuity_cid):
        conversation_manager.append_user_message(cid, "我想住龙湖时代天街")
    conversation_manager.append_user_message(ambiguous_cid, "我想住龙湖时代天街和另一处住所")
    property_manager.create(ambiguous_cid, Property(
        title="另一处住所", geographic_identity="成都市另一处住所",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.921, lat=30.754,
    ))

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            if "Grounded residences:" in prompt:
                current = prompt.split("Current message: ", 1)[1].split("\n", 1)[0]
                requirement = "预算2000，两室一厅" in current
                focus = 'Focused residence id (context evidence only): "' in prompt
                explicit = "龙湖时代天街这个住所" in current
                continuity = "我想住龙湖时代天街" in prompt
                ambiguous = "另一处住所" in prompt
                evidence = (
                    "龙湖时代天街这个住所" if explicit else
                    "我想住龙湖时代天街" if continuity else None
                )
                return json.dumps({
                    "claim_nature": "PERSONAL_REQUIREMENT" if requirement else "PROPERTY_REALITY",
                    "layout_requirement": "两室一厅" if requirement else None,
                    "reality_type": None if requirement else "LAYOUT",
                    "claim_quote": None if requirement else "两室一厅",
                    "property_id": None if requirement or (ambiguous and not focus) else (
                        next(home.id for home in homes.values() if home.id in prompt)
                        if focus else homes[explicit_cid].id if explicit else homes[continuity_cid].id
                    ),
                    "binding_evidence": None if requirement or focus else evidence,
                    "binding_source": None if requirement else "FOCUS" if focus else "USER_EXPRESSION",
                    "attention_property_id": (
                        homes[requirement_cid].id if requirement else
                        homes[ambiguous_cid].id if ambiguous else
                        homes[explicit_cid].id if explicit else None
                    ),
                    "attention_evidence": (
                        "我想住龙湖时代天街" if requirement else
                        "我想住龙湖时代天街和另一处住所" if ambiguous else
                        "龙湖时代天街这个住所" if explicit else None
                    ),
                }, ensure_ascii=False)
            return json.dumps({
                "unknown_reference": None, "reality_type": "LAYOUT", "value": "两室一厅",
            }, ensure_ascii=False)

    monkeypatch.setattr(user_reality_return, "_intelligence", Intelligence())
    monkeypatch.setattr(profile_intelligence, "analyze", lambda *_args, **_kwargs:
                        ProfileAnalysis(patch=LivingProfilePatch(budget=2000)))
    monkeypatch.setattr(decision_signal_intelligence, "analyze", lambda *_args:
                        DecisionGeography())
    monkeypatch.setattr(decision_geography_service, "apply", lambda *args, **kwargs: None)
    monkeypatch.setattr(chat_service, "_update_profile", lambda **kwargs:
                        (profile_manager.merge(kwargs["conversation_id"], LivingProfilePatch(budget=2000), []), ())[1])
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *a: iter(["reply"]))
    reconsidered = []
    monkeypatch.setattr(living_meaning_service, "form", lambda cid, property_id:
                        reconsidered.append((cid, property_id)))

    requirement = client.post("/api/chat/stream", json={
        "conversation_id": requirement_cid, "message": "预算2000，两室一厅",
    })
    assert requirement.status_code == 200
    assert f'"focus_property_id": "{homes[requirement_cid].id}"' in requirement.text
    assert "property-grounding-response" not in requirement.text
    assert property_manager.list(requirement_cid)[0].layout_expression is None
    assert client.get(f"/api/profiles/{requirement_cid}").json()["budget"] == 2000
    assert reconsidered == [(requirement_cid, homes[requirement_cid].id)]

    explicit = client.post("/api/chat/stream", json={
        "conversation_id": explicit_cid, "message": "龙湖时代天街这个住所是两室一厅",
    })
    assert explicit.status_code == 200
    assert "focus_property_id" not in explicit.text
    assert property_manager.list(explicit_cid)[0].layout_expression == "两室一厅"

    continuity = client.post("/api/chat/stream", json={
        "conversation_id": continuity_cid, "message": "这个住所是两室一厅",
    })
    assert continuity.status_code == 200
    assert property_manager.list(continuity_cid)[0].layout_expression == "两室一厅"

    ambiguous = client.post("/api/chat/stream", json={
        "conversation_id": ambiguous_cid, "message": "这个住所是两室一厅",
    })
    assert ambiguous.status_code == 200
    assert "focus_property_id" not in ambiguous.text
    assert "event: property-grounding-response" in ambiguous.text
    assert all(home.layout_expression is None for home in property_manager.list(ambiguous_cid))

    focused_requirement = client.post("/api/chat/stream", json={
        "conversation_id": focused_cid, "message": "预算2000，两室一厅",
        "user_reality_property_id": homes[focused_cid].id,
    })
    assert focused_requirement.status_code == 200
    assert property_manager.list(focused_cid)[0].layout_expression is None

    focused = client.post("/api/chat/stream", json={
        "conversation_id": focused_cid, "message": "这个住所是两室一厅",
        "user_reality_property_id": homes[focused_cid].id,
    })
    assert focused.status_code == 200
    assert property_manager.list(focused_cid)[0].layout_expression == "两室一厅"
    assert len(reconsidered) == 5
    assert all(property_manager.list(cid)[0].rent is None for cid in ids)


def test_focused_layout_statement_persists_without_inventing_rent(monkeypatch):
    client = TestClient(app)
    cid = uuid_for("focused-layout-with-budget")
    create_owned_conversation(client, cid)
    profile_store.save(cid, LivingProfile())
    home = property_manager.create(cid, Property(
        title="龙湖时代天街", geographic_identity="成都市龙湖时代天街",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.920730, lat=30.753792,
    ))
    property_manager.update_living_meaning(
        home.id, cid, meaning="stale meaning", reality_hash="old-layout",
    )
    property_manager.update_current_judgment(
        home.id, cid, judgment="stale judgment", state_hash="old-layout",
    )

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            assert "龙湖时代天街" in prompt
            if "Grounded residences:" in prompt:
                return json.dumps({
                    "claim_nature": "PROPERTY_REALITY", "reality_type": "LAYOUT",
                    "claim_quote": "两室一厅", "property_id": home.id,
                    "binding_evidence": None, "binding_source": "FOCUS",
                }, ensure_ascii=False)
            if 'Current user message: "这个住所是两室一厅，预算2000"' in prompt:
                return json.dumps({
                    "unknown_reference": None, "reality_type": "LAYOUT",
                    "value": "两室一厅",
                }, ensure_ascii=False)
            return json.dumps({
                "unknown_reference": None, "reality_type": "NONE", "value": None,
            })

    monkeypatch.setattr(user_reality_return, "_intelligence", Intelligence())
    monkeypatch.setattr(
        profile_intelligence, "audit_explicit_budget",
        lambda _history: BudgetRealityAudit("CONFIRMED", 2000, "预算2000"),
    )
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *a: iter(["reply"]))
    interpretation = []
    original_form = living_meaning_service.form

    def record_interpretation(conversation_id, property_id):
        current = property_manager.get_scoped(property_id, conversation_id)
        interpretation.append((
            profile_store.get(conversation_id).budget,
            current.layout_expression, current.living_meaning, current.current_judgment,
        ))
        return original_form(conversation_id, property_id)

    monkeypatch.setattr(living_meaning_service, "form", record_interpretation)
    assert user_reality_return.admit(cid, home.id, "我希望两室一厅") is None
    assert property_manager.get_scoped(home.id, cid).layout_expression is None
    response = client.post("/api/chat/stream", json={
        "conversation_id": cid, "message": "这个住所是两室一厅，预算2000",
        "user_reality_property_id": home.id,
    })
    assert response.status_code == 200
    assert response.text.count("world-consequence-ready") == 2
    assert interpretation == [(2000, "两室一厅", None, None)]
    assert client.get(f"/api/profiles/{cid}").json()["budget"] == 2000
    stored = property_manager.get_scoped(home.id, cid)
    assert stored is not None and stored.id == home.id
    assert stored.layout_expression == "两室一厅"
    assert stored.layout_source == "USER_PROVIDED"
    assert stored.rent is None and stored.rent_source is None
    assert stored.living_meaning is None and stored.current_judgment is None
    items = client.get(f"/api/properties?conversation_id={cid}").json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == home.id
    assert items[0]["layout_expression"] == "两室一厅"
    assert items[0]["layout_source"] == "USER_PROVIDED"


def test_active_tenancy_unknown_answer_updates_world(monkeypatch):
    client = TestClient(app)
    cid = uuid_for("tenancy-unknown-return")
    create_owned_conversation(client, cid)
    profile_store.save(cid, LivingProfile())
    home = property_manager.create(cid, Property(
        title="龙湖时代天街", geographic_identity="龙湖时代天街",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.920730, lat=30.753792,
    ))
    property_manager.update_confirmed_rent(home.id, cid, 2200)
    question = "这住所是整租还是与他人合租？"
    property_manager.update_meaningful_unknown(
        home.id, cid, question=question, why="租住方式尚未确认",
        state_hash="tenancy-question",
    )
    meaning = "已确认整租和月租，是否符合个人需要仍未知。"
    judgment = "租住安排已明确，其个人适配性仍待了解。"
    calls = []

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            if "Grounded residences:" in prompt:
                return json.dumps({
                    "claim_nature": "PROPERTY_REALITY", "reality_type": "TENANCY_MODE",
                    "claim_quote": "整租", "property_id": home.id,
                    "binding_evidence": None, "binding_source": "FOCUS",
                }, ensure_ascii=False)
            if "Determine whether the CURRENT user message" in prompt:
                assert question in prompt
                assert 'Current user message: "整租"' in prompt
                assert "龙湖时代天街" in prompt
                return json.dumps({"unknown_reference": question,
                                   "reality_type": "TENANCY_MODE",
                                   "value": "ENTIRE_RENT"})
            assert '"TENANCY_MODE_REALITY": "ENTIRE_RENT"' in prompt
            grounding = [
                {"fact": "TENANCY_MODE_REALITY", "value": "ENTIRE_RENT"},
                {"fact": "RENT_REALITY", "value": "2200 CNY/month"},
            ]
            if "Audit whether EVERY claim" in prompt:
                assert "personal value, pressure, priority, or a trade-off" in prompt
                return json.dumps({"supported": True, "unsupported_claims": []})
            if "Identify the ONE unknown Reality" in prompt:
                calls.append("unknown")
                return "null"
            if "Judge whether the CURRENT Possible Life" in prompt:
                calls.append("readiness")
                return json.dumps({"status": "NEED_MORE_REALITY",
                                   "reason": "个人需要尚未知",
                                   "meaning_reference": meaning,
                                   "judgment_reference": judgment,
                                   "grounding": grounding})
            if "Form one provisional Current Judgment" in prompt:
                calls.append("judgment")
                return json.dumps({"judgment": judgment,
                                   "meaning_reference": meaning,
                                   "grounding": grounding})
            calls.append("meaning")
            return json.dumps({"meaning": meaning, "grounding": grounding})

    intelligence = Intelligence()
    monkeypatch.setattr(user_reality_return, "_intelligence", intelligence)
    monkeypatch.setattr(living_meaning_service, "_intelligence", intelligence)
    monkeypatch.setattr(chat_service, "_update_profile", lambda *a, **kw: None)
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *a: iter(["reply"]))
    response = client.post("/api/chat/stream", json={
        "conversation_id": cid, "message": "整租",
        "user_reality_property_id": home.id,
    })
    assert response.status_code == 200
    assert response.text.count("world-consequence-ready") == 2
    restored = property_manager.get_scoped(home.id, cid)
    assert restored.tenancy_mode == "ENTIRE_RENT"
    assert restored.tenancy_mode_source == "USER_PROVIDED"
    assert restored.meaningful_unknown is None
    assert restored.living_meaning == meaning
    assert restored.current_judgment == judgment
    assert restored.decision_readiness == "NEED_MORE_REALITY"
    assert calls == ["meaning", "judgment", "readiness", "unknown"]
    assert client.get(f"/api/properties?conversation_id={cid}").json()["items"][0]["tenancy_mode"] == "ENTIRE_RENT"


def test_active_bathroom_unknown_answer_updates_world(monkeypatch):
    client = TestClient(app)
    cid = uuid_for("bathroom-unknown-return")
    create_owned_conversation(client, cid)
    profile_store.save(cid, LivingProfile())
    home = property_manager.create(cid, Property(
        title="龙湖时代天街", geographic_identity="龙湖时代天街",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.920730, lat=30.753792,
    ))
    property_manager.update_confirmed_rent(home.id, cid, 2200)
    question = "你租住的房间是否带独立卫生间？"
    property_manager.update_meaningful_unknown(
        home.id, cid, question=question, why="卫生间安排尚未确认",
        state_hash="bathroom-question",
    )
    assert property_manager.admit_user_bathroom_reality(
        home.id, cid, unknown_hash="stale", independent_bathroom=True,
    ) is None
    assert property_manager.get_scoped(home.id, cid).independent_bathroom is None
    property_manager.update_living_meaning(
        home.id, cid, meaning="old meaning", reality_hash="old-world",
    )
    property_manager.update_current_judgment(
        home.id, cid, judgment="old judgment", state_hash="old-world",
    )
    property_manager.update_meaningful_unknown(
        home.id, cid, question=question, why="卫生间安排尚未确认",
        state_hash="bathroom-question",
    )
    meaning = "已确认独立卫生间和月租，是否符合个人需要仍未知。"
    judgment = "卫生间安排已明确，其个人适配性仍待了解。"
    calls = []
    unsupported = "独立卫生间隐私更好，更适合用户，也更划算。"
    rejected = []

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            if "Grounded residences:" in prompt:
                return json.dumps({
                    "claim_nature": "PROPERTY_REALITY",
                    "reality_type": "INDEPENDENT_BATHROOM",
                    "claim_quote": "独立卫生间", "property_id": home.id,
                    "binding_evidence": None, "binding_source": "FOCUS",
                }, ensure_ascii=False)
            if "Determine whether the CURRENT user message" in prompt:
                assert question in prompt
                assert 'Current user message: "独立卫生间"' in prompt
                assert "龙湖时代天街" in prompt
                return json.dumps({"unknown_reference": question,
                                   "reality_type": "INDEPENDENT_BATHROOM",
                                   "value": True})
            assert '"INDEPENDENT_BATHROOM_REALITY": "PRESENT"' in prompt
            grounding = [
                {"fact": "INDEPENDENT_BATHROOM_REALITY", "value": "PRESENT"},
                {"fact": "RENT_REALITY", "value": "2200 CNY/month"},
            ]
            if "Audit whether EVERY claim" in prompt:
                assert "personal value, pressure, priority, or a trade-off" in prompt
                if unsupported in prompt:
                    rejected.append(unsupported)
                    return json.dumps({"supported": False,
                                       "unsupported_claims": [unsupported]})
                return json.dumps({"supported": True, "unsupported_claims": []})
            if "Identify the ONE unknown Reality" in prompt:
                calls.append("unknown")
                return "null"
            if "Judge whether the CURRENT Possible Life" in prompt:
                calls.append("readiness")
                return json.dumps({"status": "NEED_MORE_REALITY",
                                   "reason": "个人需要尚未知",
                                   "meaning_reference": meaning,
                                   "judgment_reference": judgment,
                                   "grounding": grounding})
            if "Form one provisional Current Judgment" in prompt:
                calls.append("judgment")
                return json.dumps({"judgment": judgment,
                                   "meaning_reference": meaning,
                                   "grounding": grounding})
            calls.append("meaning")
            return json.dumps({"meaning": meaning if rejected else unsupported,
                               "grounding": grounding})

    intelligence = Intelligence()
    monkeypatch.setattr(user_reality_return, "_intelligence", intelligence)
    monkeypatch.setattr(living_meaning_service, "_intelligence", intelligence)
    monkeypatch.setattr(chat_service, "_update_profile", lambda *a, **kw: None)
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *a: iter(["reply"]))
    response = client.post("/api/chat/stream", json={
        "conversation_id": cid, "message": "独立卫生间",
        "user_reality_property_id": home.id,
    })
    assert response.status_code == 200
    assert response.text.count("world-consequence-ready") == 2
    restored = property_manager.get_scoped(home.id, cid)
    assert restored.independent_bathroom is True
    assert restored.independent_bathroom_source == "USER_PROVIDED"
    assert restored.meaningful_unknown is None
    assert restored.living_meaning == meaning
    assert restored.current_judgment == judgment
    assert restored.decision_readiness == "NEED_MORE_REALITY"
    assert calls == ["meaning", "meaning", "judgment", "readiness", "unknown"]
    assert rejected == [unsupported]
    assert unsupported not in (restored.living_meaning, restored.current_judgment)
    assert client.get(f"/api/properties?conversation_id={cid}").json()["items"][0]["independent_bathroom"] is True


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
            if "Grounded residences:" in prompt:
                sound = "路上的车声" in prompt
                return json.dumps({
                    "claim_nature": "PROPERTY_REALITY",
                    "reality_type": "INDOOR_SOUND_OBSERVATION" if sound else "INDEPENDENT_KITCHEN",
                    "claim_quote": (
                        "晚上去看了，关窗以后还是能明显听到路上的车声。"
                        if sound else "有独立厨房"
                    ),
                    "property_id": home.id,
                    "binding_evidence": None, "binding_source": "FOCUS",
                }, ensure_ascii=False)
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
