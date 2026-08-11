from app.models.conversation import ConversationMessage
from app.models.profile import LivingProfile
from app.runtime.runtime import SYSTEM_PROMPT, AIRuntime


def test_conversation_prompt_guides_understanding_analysis_and_next_action() -> None:
    assert "Confirm what you currently understand" in SYSTEM_PROMPT
    assert "Identify only missing information" in SYSTEM_PROMPT
    assert "Guide the user toward the most useful next action" in SYSTEM_PROMPT
    assert "Do not use rigid section" in SYSTEM_PROMPT
    assert "headings" in SYSTEM_PROMPT
    assert "When the known information is sufficient to move forward" in SYSTEM_PROMPT
    assert "Prefer one low-risk, easy-to-correct assumption" in SYSTEM_PROMPT
    assert "Ask only one question" in SYSTEM_PROMPT
    assert "give the current judgment first" in SYSTEM_PROMPT
    assert "Every reply must make progress" in SYSTEM_PROMPT


def test_decision_guidance_stops_collection_when_information_is_sufficient() -> None:
    assert "stop collecting" in SYSTEM_PROMPT
    assert "concrete next action" in SYSTEM_PROMPT


def test_decision_guidance_allows_a_low_risk_assumption() -> None:
    assert "State the assumption naturally" in SYSTEM_PROMPT
    assert "invite correction" in SYSTEM_PROMPT


def test_decision_guidance_limits_questions_to_material_missing_facts() -> None:
    assert "materially change the next" in SYSTEM_PROMPT
    assert "Explain why that fact matters" in SYSTEM_PROMPT


def test_decision_guidance_handles_a_challenged_judgment() -> None:
    assert "challenges your judgment" in SYSTEM_PROMPT
    assert "explain the trade-off" in SYSTEM_PROMPT
    assert "still give the next action" in SYSTEM_PROMPT
    assert "not a signal to restart" in SYSTEM_PROMPT
    assert "collection" in SYSTEM_PROMPT


def test_complete_profile_context_points_toward_property_analysis() -> None:
    runtime = AIRuntime()
    context = runtime.build_context(
        [ConversationMessage(role="user", content="我想找适合自己的房子。")],
        LivingProfile(
            work_location="南山区",
            budget=6000,
            commute_minutes=30,
            preferred_city="深圳",
            family_size=1,
            has_pet=False,
        ),
    )

    profile_context = context[1]["content"]
    assert "工作地点: 南山区" in profile_context
    assert "预算: 6000" in profile_context
    assert "通勤时长: 30" in profile_context
    assert "Treat these as confirmed facts" in profile_context


def test_partial_profile_context_contains_only_known_facts() -> None:
    runtime = AIRuntime()
    context = runtime.build_context(
        [ConversationMessage(role="user", content="我在南山上班。")],
        LivingProfile(work_location="南山区"),
    )

    profile_context = context[1]["content"]
    assert "工作地点: 南山区" in profile_context
    assert "预算:" not in profile_context
    assert "通勤时长:" not in profile_context


def test_changed_profile_is_marked_as_correctable_prior_understanding() -> None:
    runtime = AIRuntime()
    context = runtime.build_context(
        [ConversationMessage(role="user", content="预算改成8000元。")],
        LivingProfile(budget=8000),
    )

    assert "invite correction" in context[1]["content"]


def test_new_conversation_can_reuse_existing_profile_without_history() -> None:
    runtime = AIRuntime()
    context = runtime.build_context(
        [],
        LivingProfile(work_location="南山区", budget=6000),
    )

    assert len(context) == 2
    assert "工作地点: 南山区" in context[1]["content"]
    assert "预算: 6000" in context[1]["content"]
