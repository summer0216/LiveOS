import json

import pytest

from app.models.profile_patch import LivingProfilePatch
from app.runtime.runtime import AIRuntime
from app.services.conversation_manager import conversation_manager
from app.services.profile_intelligence import profile_intelligence
from app.services.profile_manager import profile_manager
from app.services.resume_resolver import resume_resolver
from app.stores.runtime import conversation_store
from tests.ids import uuid_for


def analysis_json(
    *,
    clear_fields: list[str] | None = None,
    work_location: str | None = None,
    budget: int | None = None,
    commute_minutes: int | None = None,
    feedback_relevant: bool = False,
    observed_commute_minutes: int | None = None,
) -> str:
    return json.dumps(
        {
            "work_location": work_location,
            "budget": budget,
            "commute_minutes": commute_minutes,
            "preferred_city": None,
            "family_size": None,
            "has_pet": None,
            "clear_fields": clear_fields or [],
            "decision_relevant_feedback": {
                "relevant": feedback_relevant,
                "observation": (
                    "实测通勤约80分钟。" if observed_commute_minutes else None
                ),
                "judgment": (
                    "unacceptable" if observed_commute_minutes else None
                ),
                "observed_commute_minutes": observed_commute_minutes,
            },
        },
        ensure_ascii=False,
    )


def test_profile_intelligence_extracts_set_and_correction() -> None:
    replacement = profile_intelligence._build_analysis(
        analysis_json(budget=4500),
        "预算改成4500元。",
    )
    correction = profile_intelligence._build_analysis(
        analysis_json(work_location="前海"),
        "我刚才说错了，我其实在前海工作。",
    )

    assert replacement.patch.budget == 4500
    assert replacement.patch.clear_fields == frozenset()
    assert correction.patch.work_location == "前海"
    assert correction.patch.clear_fields == frozenset()


def test_profile_intelligence_distinguishes_clear_from_no_change() -> None:
    cleared = profile_intelligence._build_analysis(
        analysis_json(clear_fields=["budget"]),
        "预算我现在还没想好，先不要按3000元算。",
    )
    no_change = profile_intelligence._build_analysis(
        analysis_json(clear_fields=["budget"]),
        "好的，我们继续看看。",
    )

    assert cleared.patch.budget is None
    assert cleared.patch.clear_fields == frozenset({"budget"})
    assert no_change.patch.budget is None
    assert no_change.patch.clear_fields == frozenset()


def test_observed_commute_cannot_set_or_clear_preference() -> None:
    analysis = profile_intelligence._build_analysis(
        analysis_json(
            clear_fields=["commute_minutes"],
            commute_minutes=80,
            feedback_relevant=True,
            observed_commute_minutes=80,
        ),
        "我今天实际通勤80分钟，我接受不了。",
    )

    assert analysis.patch.commute_minutes is None
    assert "commute_minutes" not in analysis.patch.clear_fields
    assert analysis.decision_feedback.observed_commute_minutes == 80


def test_profile_intelligence_extracts_explicit_commute_preference_clear() -> None:
    analysis = profile_intelligence._build_analysis(
        analysis_json(clear_fields=["commute_minutes"]),
        "通勤时间先不设限制了，之前65分钟的要求取消。",
    )

    assert analysis.patch.commute_minutes is None
    assert analysis.patch.clear_fields == frozenset({"commute_minutes"})


def test_profile_merge_supports_set_clear_no_change_and_reset() -> None:
    conversation_id = uuid_for("profile-mutation-set-clear-reset")
    conversation_manager.get_or_create(conversation_id)

    profile, changed = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(budget=3000, work_location="南山"),
        [],
    )
    assert profile.budget == 3000
    assert profile.work_location == "南山"
    assert changed is True

    profile, changed = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(budget=4500, work_location="前海"),
        [],
    )
    assert profile.budget == 4500
    assert profile.work_location == "前海"
    assert changed is True

    profile, changed = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(clear_fields=frozenset({"budget"})),
        [],
    )
    assert profile.budget is None
    assert changed is True
    assert profile_manager.get(conversation_id).budget is None

    profile, changed = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(clear_fields=frozenset({"budget"})),
        [],
    )
    assert profile.budget is None
    assert changed is False

    profile, changed = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(),
        [],
    )
    assert profile.budget is None
    assert changed is False

    profile, changed = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(budget=3500),
        [],
    )
    assert profile.budget == 3500
    assert changed is True


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("work_location", "南山"),
        ("budget", 3000),
        ("commute_minutes", 65),
        ("preferred_city", "深圳"),
        ("family_size", 1),
        ("has_pet", False),
    ],
)
def test_clear_applies_to_every_mutable_profile_field(
    field_name: str,
    value: object,
) -> None:
    conversation_id = uuid_for(f"profile-mutation-clear-{field_name}")
    conversation_manager.get_or_create(conversation_id)
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(**{field_name: value}),
        [],
    )

    profile, changed = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(clear_fields=frozenset({field_name})),
        [],
    )

    assert getattr(profile, field_name) is None
    assert changed is True


def test_cleared_profile_is_absent_from_runtime_and_resume() -> None:
    conversation_id = uuid_for("profile-mutation-runtime-resume")
    conversation_manager.get_or_create(conversation_id)
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(budget=3000, work_location="南山"),
        [],
    )
    profile, changed = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(clear_fields=frozenset({"budget"})),
        [],
    )

    assert changed is True
    runtime_context = AIRuntime._living_profile_context(profile)
    assert "工作地点: 南山" in runtime_context
    assert "预算:" not in runtime_context

    owner_id = conversation_store.owner_id(conversation_id)
    assert owner_id is not None
    resumed = resume_resolver.resolve_conversation(owner_id, conversation_id)
    assert resumed is not None
    assert resumed.profile is not None
    assert resumed.profile.budget is None
