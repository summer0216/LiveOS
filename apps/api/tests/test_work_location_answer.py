import json
from types import SimpleNamespace

import pytest

from app.models.conversation import ConversationMessage
from app.models.decision_geography import DecisionGeography
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus
from app.services.chat_service import ChatService
from app.services.profile_intelligence import profile_intelligence


@pytest.mark.parametrize("clicked,precision,expected", [
    (True, GeographicPrecision.AREA, True),
    (False, GeographicPrecision.AREA, False),
    (True, GeographicPrecision.PLACE, False),
])
def test_stream_passes_selected_work_role_to_both_extractors(
    monkeypatch, clicked, precision, expected,
):
    service = ChatService()
    calls = []
    history = [ConversationMessage(role="user", content="融科资讯中心")]
    monkeypatch.setattr(service, "_prepare_conversation", lambda **_: (None, history))
    monkeypatch.setattr("app.services.chat_service.property_manager.list", lambda _: [])
    monkeypatch.setattr("app.services.chat_service.profile_manager.get", lambda _: SimpleNamespace(
        geographic_status=GeographicStatus.GROUNDED,
        geographic_precision=precision, commute_minutes=30,
    ))

    def profile(messages, properties, **options):
        assert messages[-1].content == "融科资讯中心"
        calls.append(("profile", options.get("work_location_answer", False)))
        return ProfileAnalysis(patch=LivingProfilePatch())

    def signal(message, **options):
        assert message == "融科资讯中心"
        calls.append(("signal", options.get("work_location_answer", False)))
        return DecisionGeography()

    def complete(*args):
        args[3].result()
        args[4].shutdown(wait=True)
        return iter(())

    monkeypatch.setattr("app.services.chat_service.profile_intelligence.analyze", profile)
    monkeypatch.setattr("app.services.chat_service.decision_signal_intelligence.analyze", signal)
    monkeypatch.setattr("app.services.chat_service.decision_geography_service.apply", lambda *a, **k: None)
    monkeypatch.setattr(service, "_complete_stream_turn", complete)
    list(service.chat_stream(
        "conversation", "融科资讯中心",
        clarification_target="WORK_LOCATION" if clicked else None,
    ))
    assert sorted(calls) == [("profile", expected), ("signal", expected)]


@pytest.mark.parametrize("extracted,expected", [
    ("融科资讯中心", "融科资讯中心"),
    ("旧的工作地点", None),
    (None, None),
])
def test_work_answer_cannot_promote_a_place_absent_from_user_answer(
    monkeypatch, extracted, expected,
):
    prompts = []

    def generate(prompt):
        prompts.append(prompt)
        return json.dumps({"work_location": extracted})

    monkeypatch.setattr("app.services.profile_intelligence.ai_client.generate_json", generate)
    result = profile_intelligence.analyze(
        [ConversationMessage(role="user", content="融科资讯中心")],
        work_location_answer=True,
    )
    assert result.patch.work_location == expected
    assert "explicitly selected" in prompts[0]


def test_work_role_does_not_bypass_decision_geography_truth_guard():
    result = profile_intelligence._build_decision_geography({
        "decision_intent": {"established": True, "type": "work_location"},
        "decision_geography": {"identity": "旧地点", "source": "USER"},
    }, "融科资讯中心")
    assert not result.intent_established
