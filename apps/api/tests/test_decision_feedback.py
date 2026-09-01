import json

from app.api.chat import _stream_events
from app.models.decision_feedback import DecisionRelevantFeedback
from app.runtime.decision import format_current_feedback
from app.schemas.decision import DecisionReason, DecisionResult
from app.services.decision_context_builder import decision_context_builder
from app.services.decision_feedback_context import decision_feedback_context
from app.services.decision_service import (
    apply_decision_feedback,
    build_next_actions,
)
from app.services.profile_intelligence import profile_intelligence
from tests.ids import uuid_for


def analysis_json(
    *,
    commute_minutes: int | None,
    relevant: bool,
    observation: str | None = None,
    judgment: str | None = None,
    observed_commute_minutes: int | None = None,
) -> str:
    return json.dumps(
        {
            "work_location": None,
            "budget": None,
            "commute_minutes": commute_minutes,
            "preferred_city": None,
            "family_size": None,
            "has_pet": None,
            "decision_relevant_feedback": {
                "relevant": relevant,
                "observation": observation,
                "judgment": judgment,
                "observed_commute_minutes": observed_commute_minutes,
            },
        },
        ensure_ascii=False,
    )


def test_observed_commute_does_not_overwrite_commute_preference() -> None:
    analysis = profile_intelligence._build_analysis(
        analysis_json(
            commute_minutes=80,
            relevant=True,
            observation="早高峰实测通勤约80分钟。",
            judgment="unacceptable",
            observed_commute_minutes=80,
        ),
        "我今天早高峰试了一下，实际差不多80分钟，我接受不了。",
    )

    assert analysis.patch.commute_minutes is None
    assert analysis.decision_feedback.relevant is True
    assert analysis.decision_feedback.observed_commute_minutes == 80
    assert analysis.decision_feedback.judgment == "unacceptable"


def test_explicit_commute_preference_change_may_update_profile() -> None:
    analysis = profile_intelligence._build_analysis(
        analysis_json(commute_minutes=40, relevant=False),
        "以后我最多只能接受40分钟通勤。",
    )

    assert analysis.patch.commute_minutes == 40
    assert analysis.decision_feedback.relevant is False


def test_confirming_feedback_is_relevant_without_profile_corruption() -> None:
    analysis = profile_intelligence._build_analysis(
        analysis_json(
            commute_minutes=65,
            relevant=True,
            observation="实测通勤约65分钟。",
            judgment="acceptable",
            observed_commute_minutes=65,
        ),
        "65分钟我实际试过，可以接受。",
    )

    assert analysis.patch.commute_minutes is None
    assert analysis.decision_feedback.relevant is True
    assert analysis.decision_feedback.judgment == "acceptable"


def test_generic_acknowledgement_is_not_decision_relevant() -> None:
    analysis = profile_intelligence._build_analysis(
        analysis_json(commute_minutes=None, relevant=False),
        "好的，我知道了。",
    )

    assert analysis.patch.commute_minutes is None
    assert analysis.decision_feedback.relevant is False


def test_decision_context_receives_bounded_feedback_once() -> None:
    conversation_id = uuid_for("decision-feedback-context")
    feedback = DecisionRelevantFeedback(
        relevant=True,
        observation="早高峰实测通勤约80分钟。",
        judgment="unacceptable",
        observed_commute_minutes=80,
    )
    decision_feedback_context.set(conversation_id, feedback)

    first_context = decision_context_builder.build(conversation_id)
    second_context = decision_context_builder.build(conversation_id)

    assert first_context.current_feedback == feedback
    prompt_section = format_current_feedback(first_context)
    assert "早高峰实测通勤约80分钟" in prompt_section
    assert "unacceptable" in prompt_section
    assert second_context.current_feedback is None


def test_feedback_signal_uses_existing_stream_without_assistant_content() -> None:
    conversation_id = uuid_for("decision-feedback-stream")
    decision_feedback_context.set(
        conversation_id,
        DecisionRelevantFeedback(
            relevant=True,
            observation="实测通勤约80分钟。",
            judgment="unacceptable",
            observed_commute_minutes=80,
        ),
    )

    events = list(_stream_events(iter(["assistant reply"]), conversation_id))

    assert events == [
        ": connected\n\n",
        "event: decision-feedback\ndata: true\n\n",
        'data: "assistant reply"\n\n',
    ]
    decision_feedback_context.clear(conversation_id)


def test_negative_feedback_updates_decision_and_one_next_action() -> None:
    result = DecisionResult(
        status="ready",
        summary="独立居住可行，但需要接受约65分钟通勤。",
        best_property_id="property-1",
        reasons=[DecisionReason(title="当前判断", description="原始判断。")],
        trade_offs=[],
        confidence=0.8,
    )
    feedback = DecisionRelevantFeedback(
        relevant=True,
        observation="早高峰实测通勤约80分钟，用户明确无法接受。",
        judgment="unacceptable",
        observed_commute_minutes=80,
    )

    reconsidered = apply_decision_feedback(result, feedback)
    recommendation = build_next_actions(
        reconsidered,
        None,
        None,
        None,
        feedback,
    )

    assert recommendation.summary is not None
    decision, next_action = recommendation.summary.split("下一步：", 1)
    assert "80 分钟且无法接受" in decision
    assert "通勤时间更短" in next_action
    assert "通勤更短" in reconsidered.decision_gap
    assert recommendation.summary.count("下一步：") == 1


def test_acceptable_feedback_keeps_decision_coherent_with_one_next_action() -> None:
    result = DecisionResult(
        status="ready",
        summary="独立居住可行，但需要接受约65分钟通勤。",
        best_property_id="property-1",
        reasons=[DecisionReason(title="当前判断", description="原始判断。")],
        trade_offs=[],
        confidence=0.8,
    )
    feedback = DecisionRelevantFeedback(
        relevant=True,
        observation="实测通勤约65分钟，用户确认可以接受。",
        judgment="acceptable",
        observed_commute_minutes=65,
    )

    reconsidered = apply_decision_feedback(result, feedback)
    recommendation = build_next_actions(
        reconsidered,
        None,
        None,
        None,
        feedback,
    )

    assert recommendation.summary is not None
    decision, next_action = recommendation.summary.split("下一步：", 1)
    assert "65 分钟通勤且可以接受" in decision
    assert "继续比较当前区域" in next_action
    assert "租金和居住条件" in reconsidered.decision_gap
    assert recommendation.summary.count("下一步：") == 1


def test_non_relevant_feedback_emits_no_refresh_signal() -> None:
    conversation_id = uuid_for("decision-feedback-acknowledgement")
    decision_feedback_context.clear(conversation_id)

    assert list(_stream_events(iter(["ack"]), conversation_id)) == [
        ": connected\n\n",
        'data: "ack"\n\n',
    ]
