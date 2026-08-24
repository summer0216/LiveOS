import json

from app.api.chat import _stream_events
from app.models.decision_change import FeedbackCause, ProfileMutationCause
from app.models.profile_patch import LivingProfilePatch
from app.services.conversation_manager import conversation_manager
from app.services.decision_change import (
    decision_change_context,
    format_decision_change,
)
from app.services.profile_manager import profile_manager
from tests.ids import uuid_for


def test_profile_set_and_correction_preserve_bounded_causes() -> None:
    conversation_id = uuid_for("decision-change-set-correction")
    conversation_manager.get_or_create(conversation_id)
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(budget=3000, work_location="南山"),
        [],
    )

    result = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(budget=4500, work_location="前海"),
        [],
    )

    assert result.changed is True
    assert [(cause.field, cause.operation) for cause in result.causes] == [
        ("work_location", "SET"),
        ("budget", "SET"),
    ]
    assert result.causes[0].before == "南山"
    assert result.causes[0].after == "前海"
    assert result.causes[1].before == 3000
    assert result.causes[1].after == 4500
    assert format_decision_change(result.causes) == (
        "工作地点从南山调整为前海。预算从¥3,000调整为¥4,500。"
    )


def test_profile_clear_has_product_safe_explanation() -> None:
    conversation_id = uuid_for("decision-change-clear")
    conversation_manager.get_or_create(conversation_id)
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(budget=3000),
        [],
    )

    result = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(clear_fields=frozenset({"budget"})),
        [],
    )

    assert result.changed is True
    assert len(result.causes) == 1
    cause = result.causes[0]
    assert cause.operation == "CLEAR"
    assert cause.before == 3000
    assert cause.after is None
    explanation = format_decision_change(result.causes)
    assert explanation == "原预算条件已撤销。"
    assert "None" not in explanation
    assert "null" not in explanation
    assert "预算变成 0" not in explanation


def test_no_change_and_clear_already_empty_create_no_cause() -> None:
    conversation_id = uuid_for("decision-change-no-change")
    conversation_manager.get_or_create(conversation_id)

    no_change = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(),
        [],
    )
    clear_empty = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(clear_fields=frozenset({"budget"})),
        [],
    )

    assert no_change.changed is False
    assert no_change.causes == ()
    assert clear_empty.changed is False
    assert clear_empty.causes == ()


def test_feedback_explanations_are_deterministic() -> None:
    negative = FeedbackCause(
        source="DECISION_RELEVANT_FEEDBACK",
        observation="早高峰实测通勤约80分钟。",
        judgment="unacceptable",
        observed_commute_minutes=80,
    )
    confirming = FeedbackCause(
        source="DECISION_RELEVANT_FEEDBACK",
        observation="实测通勤约65分钟。",
        judgment="acceptable",
        observed_commute_minutes=65,
    )

    assert format_decision_change((negative,)) == (
        "你实际体验了约 80 分钟通勤，并确认这个时间无法接受。"
    )
    assert format_decision_change((confirming,)) == (
        "你确认实际约 65 分钟的通勤可以接受。"
    )


def test_multiple_causes_use_one_ordered_transient_stream_event() -> None:
    conversation_id = uuid_for("decision-change-multiple")
    causes = (
        ProfileMutationCause(
            source="PROFILE_MUTATION",
            field="budget",
            operation="SET",
            before=3000,
            after=4500,
        ),
        FeedbackCause(
            source="DECISION_RELEVANT_FEEDBACK",
            observation="实测通勤约80分钟。",
            judgment="unacceptable",
            observed_commute_minutes=80,
        ),
    )
    decision_change_context.set(conversation_id, causes)

    first_events = list(_stream_events(iter(["reply"]), conversation_id))
    second_events = list(_stream_events(iter(["next reply"]), conversation_id))

    assert first_events[0] == ": connected\n\n"
    assert first_events[1].startswith("event: decision-change\ndata: ")
    payload = json.loads(first_events[1].split("data: ", 1)[1])
    assert [cause["source"] for cause in payload["causes"]] == [
        "PROFILE_MUTATION",
        "DECISION_RELEVANT_FEEDBACK",
    ]
    assert payload["explanation"].startswith("预算从¥3,000调整为¥4,500。")
    assert first_events[2] == 'data: "reply"\n\n'
    assert second_events == [": connected\n\n", 'data: "next reply"\n\n']
