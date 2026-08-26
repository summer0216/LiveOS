import json

import pytest

from app.api.chat import _stream_events
from app.core.ai_client import ai_client
from app.models.decision_challenge import DecisionChallenge
from app.models.decision_change import (
    ChallengeCause,
    FeedbackCause,
    ProfileMutationCause,
)
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.runtime.decision import format_current_challenge
from app.schemas.decision import DecisionReason, DecisionResult
from app.services.conversation_manager import conversation_manager
from app.services.decision_challenge_context import decision_challenge_context
from app.services.decision_change import (
    decision_change_context,
    format_decision_change,
)
from app.services.decision_context_builder import decision_context_builder
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.profile_intelligence import profile_intelligence
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from tests.ids import uuid_for


def analysis_json(
    *,
    challenge: dict[str, object],
    budget: int | None = None,
    commute_minutes: int | None = None,
    feedback: dict[str, object] | None = None,
) -> str:
    return json.dumps(
        {
            "work_location": None,
            "budget": budget,
            "commute_minutes": commute_minutes,
            "preferred_city": None,
            "family_size": None,
            "has_pet": None,
            "clear_fields": [],
            "decision_relevant_feedback": feedback
            or {
                "relevant": False,
                "observation": None,
                "judgment": None,
                "observed_commute_minutes": None,
            },
            "decision_challenge": challenge,
        },
        ensure_ascii=False,
    )


def challenge_payload(kind: str, statement: str) -> dict[str, object]:
    return {
        "relevant": True,
        "kind": kind,
        "subject": "当前判断",
        "statement": statement,
        "target_property_id": None,
    }


def no_challenge_payload() -> dict[str, object]:
    return {
        "relevant": False,
        "kind": None,
        "subject": None,
        "statement": None,
        "target_property_id": None,
    }


def test_required_challenge_categories_are_bounded() -> None:
    scenarios = (
        ("我不太认同这个判断。", "DIRECT"),
        ("我不认同这个判断，你重新考虑一下。", "DIRECT"),
        ("我觉得65分钟通勤还是太久了，这个取舍是不是不值得？", "TRADE_OFF"),
        ("你是不是太看重预算了？", "PRIORITY"),
        ("我其实还是更倾向另一个房源。", "ALTERNATIVE"),
    )

    for message, kind in scenarios:
        analysis = profile_intelligence._build_analysis(
            analysis_json(challenge=challenge_payload(kind, message)),
            message,
        )

        assert analysis.decision_challenge.relevant is True
        assert analysis.decision_challenge.kind == kind
        assert analysis.decision_feedback.relevant is False


def test_fallback_recognizes_explicit_challenge_without_an_extra_call() -> None:
    analysis = profile_intelligence._build_analysis(
        analysis_json(challenge=no_challenge_payload()),
        "我不认同这个判断，你重新考虑一下。",
    )

    assert analysis.decision_challenge.relevant is True
    assert analysis.decision_challenge.kind == "DIRECT"


def test_explanation_and_ordinary_turns_are_not_challenges() -> None:
    for message in ("为什么你推荐这个房源？", "好的，我知道了。"):
        analysis = profile_intelligence._build_analysis(
            analysis_json(challenge=no_challenge_payload()),
            message,
        )

        assert analysis.decision_challenge.relevant is False
        assert analysis.decision_feedback.relevant is False


def test_tradeoff_challenge_does_not_set_commute_preference() -> None:
    message = "我觉得65分钟通勤还是太久了，这个取舍是不是不值得？"
    analysis = profile_intelligence._build_analysis(
        analysis_json(
            challenge=challenge_payload("TRADE_OFF", message),
            commute_minutes=65,
        ),
        message,
    )

    assert analysis.patch.commute_minutes is None
    assert analysis.decision_challenge.kind == "TRADE_OFF"


def test_priority_challenge_does_not_mutate_budget() -> None:
    message = "你是不是太看重预算了？"
    analysis = profile_intelligence._build_analysis(
        analysis_json(
            challenge=challenge_payload("PRIORITY", message),
            budget=4500,
        ),
        message,
    )

    assert analysis.patch.budget is None
    assert analysis.decision_challenge.kind == "PRIORITY"


def test_real_profile_mutation_is_preserved_alongside_challenge() -> None:
    message = "预算改成4500元，但我还是不认同你对这个区域的判断。"
    analysis = profile_intelligence._build_analysis(
        analysis_json(
            challenge=challenge_payload("DIRECT", message),
            budget=4500,
        ),
        message,
    )

    assert analysis.patch.budget == 4500
    assert analysis.decision_challenge.relevant is True

    commute_message = "通勤要求改成40分钟，但我仍然不认同当前判断。"
    commute_analysis = profile_intelligence._build_analysis(
        analysis_json(
            challenge=challenge_payload("DIRECT", commute_message),
            commute_minutes=40,
        ),
        commute_message,
    )

    assert commute_analysis.patch.commute_minutes == 40


def test_challenge_does_not_fake_feedback_but_real_feedback_is_preserved() -> None:
    fake_feedback = {
        "relevant": True,
        "observation": "用户不认同当前判断。",
        "judgment": "unacceptable",
        "observed_commute_minutes": None,
    }
    direct = profile_intelligence._build_analysis(
        analysis_json(
            challenge=challenge_payload("DIRECT", "我不认同这个判断。"),
            feedback=fake_feedback,
        ),
        "我不认同这个判断。",
    )

    real_feedback = {
        "relevant": True,
        "observation": "今天实际通勤80分钟，无法接受。",
        "judgment": "unacceptable",
        "observed_commute_minutes": 80,
    }
    combined = profile_intelligence._build_analysis(
        analysis_json(
            challenge=challenge_payload(
                "DIRECT",
                "我今天实际通勤80分钟，接受不了，而且推荐有问题。",
            ),
            commute_minutes=80,
            feedback=real_feedback,
        ),
        "我今天实际通勤80分钟，接受不了，而且我觉得推荐有问题。",
    )

    assert direct.decision_feedback.relevant is False
    assert combined.decision_feedback.relevant is True
    assert combined.decision_feedback.observed_commute_minutes == 80
    assert combined.patch.commute_minutes is None


def test_challenge_uses_ordered_transient_change_event() -> None:
    conversation_id = uuid_for("decision-challenge-change-event")
    causes = (
        ProfileMutationCause(
            source="PROFILE_MUTATION",
            field="budget",
            operation="SET",
            before=3500,
            after=4500,
        ),
        FeedbackCause(
            source="DECISION_RELEVANT_FEEDBACK",
            observation="实测通勤约80分钟。",
            judgment="unacceptable",
            observed_commute_minutes=80,
        ),
        ChallengeCause(
            source="DECISION_CHALLENGE",
            kind="DIRECT",
            subject="当前判断",
            statement="我不认同这个判断。",
            target_property_id=None,
        ),
    )
    decision_change_context.set(conversation_id, causes)

    events = list(_stream_events(iter(["reply"]), conversation_id))
    payload = json.loads(events[1].split("data: ", 1)[1])

    assert [cause["source"] for cause in payload["causes"]] == [
        "PROFILE_MUTATION",
        "DECISION_RELEVANT_FEEDBACK",
        "DECISION_CHALLENGE",
    ]
    assert payload["explanation"].endswith(
        "你对当前判断提出了质疑，已重新评估。"
    )
    assert list(_stream_events(iter(["next"]), conversation_id)) == [
        ": connected\n\n",
        'data: "next"\n\n',
    ]


def test_challenge_reaches_decision_context_once_without_conversation_history() -> None:
    conversation_id = uuid_for("decision-challenge-context")
    challenge = DecisionChallenge(
        relevant=True,
        kind="PRIORITY",
        subject="预算优先级",
        statement="你是不是太看重预算了？",
    )
    decision_challenge_context.set(conversation_id, challenge)

    first = decision_context_builder.build(conversation_id)
    second = decision_context_builder.build(conversation_id)

    assert first.current_challenge == challenge
    assert "太看重预算" in format_current_challenge(first)
    assert "must never override Grounded Evidence" in format_current_challenge(first)
    assert second.current_challenge is None
    assert not hasattr(first, "conversation_history")


def test_challenge_explanations_are_deterministic() -> None:
    causes = (
        ChallengeCause(
            source="DECISION_CHALLENGE",
            kind="TRADE_OFF",
            subject="65分钟通勤取舍",
            statement="这个取舍是不是不值得？",
            target_property_id=None,
        ),
        ChallengeCause(
            source="DECISION_CHALLENGE",
            kind="PRIORITY",
            subject="预算优先级",
            statement="你是不是太看重预算了？",
            target_property_id=None,
        ),
    )

    assert format_decision_change(causes) == (
        "你对当前取舍提出了质疑，已重新评估。"
        "你质疑当前判断中过度强调某项条件，已重新评估。"
    )


def prepare_decision_scenario(
    conversation_id: str,
) -> tuple[str, str]:
    conversation_manager.get_or_create(conversation_id)
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(
            work_location="南山科技园",
            budget=6000,
            commute_minutes=30,
            preferred_city="深圳",
            family_size=1,
            has_pet=False,
        ),
        [],
    )
    first = property_manager.create(
        conversation_id,
        Property(title="候选一", district="南山", rent=5600, commute_minutes=25),
    )
    second = property_manager.create(
        conversation_id,
        Property(title="候选二", district="福田", rent=5900, commute_minutes=20),
    )
    assert first.id is not None
    assert second.id is not None
    decision_record_service.save(
        conversation_id,
        DecisionResult(
            status="ready",
            summary="继续候选一。下一步：核实房源条件。",
            best_property_id=first.id,
            reasons=[DecisionReason(title="原判断", description="候选一当前更匹配。")],
            trade_offs=[],
            confidence=0.8,
        ),
    )
    decision_challenge_context.set(
        conversation_id,
        DecisionChallenge(
            relevant=True,
            kind="DIRECT",
            subject="当前判断",
            statement="我不认同这个判断，请重新考虑。",
        ),
    )
    return first.id, second.id


def ready_response(property_id: str, summary: str) -> str:
    return json.dumps(
        {
            "status": "ready",
            "summary": summary,
            "best_property_id": property_id,
            "reasons": [{"title": "重新评估", "description": "已重新核对当前证据。"}],
            "trade_offs": [],
            "confidence": 0.8,
        },
        ensure_ascii=False,
    )


@pytest.mark.parametrize(
    ("case", "change_property"),
    (("hold", False), ("change", True)),
)
def test_challenge_can_hold_or_change_ready_decision(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    change_property: bool,
) -> None:
    conversation_id = uuid_for(f"decision-challenge-{case}")
    first_id, second_id = prepare_decision_scenario(conversation_id)
    target_id = second_id if change_property else first_id
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return ready_response(target_id, f"重新评估后选择{target_id}。")

    monkeypatch.setattr(ai_client, "generate_json", generate)
    try:
        result = decision_service.generate(conversation_id)

        assert result.status == "ready"
        assert result.best_property_id == target_id
        assert result.summary is not None
        assert result.summary.count("下一步：") == 1
        assert "我不认同这个判断，请重新考虑" in prompts[0]
        records = decision_record_service.list(conversation_id)
        assert len(records) == 2
        assert records[0].summary == result.summary
        assert records[0].summary.count("下一步：") == 1
    finally:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)
        decision_challenge_context.clear(conversation_id)


def test_challenge_waiting_preserves_last_ready_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-challenge-waiting")
    prepare_decision_scenario(conversation_id)
    monkeypatch.setattr(
        ai_client,
        "generate_json",
        lambda _prompt: json.dumps(
            {
                "status": "waiting",
                "summary": "当前证据不足，需要进一步确认候选对象。",
                "best_property_id": None,
                "reasons": [],
                "trade_offs": [],
                "confidence": None,
            },
            ensure_ascii=False,
        ),
    )
    try:
        result = decision_service.generate(conversation_id)

        assert result.status == "waiting"
        records = decision_record_service.list(conversation_id)
        assert len(records) == 1
        assert records[0].summary == "继续候选一。下一步：核实房源条件。"
    finally:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)
        decision_challenge_context.clear(conversation_id)
