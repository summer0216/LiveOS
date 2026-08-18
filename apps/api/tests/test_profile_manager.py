from app.models.profile_patch import LivingProfilePatch
from app.services.profile_manager import profile_manager
from tests.ids import uuid_for


def test_profile_merge_and_tag_update() -> None:
    conversation_id = uuid_for("profile-manager")
    profile_manager.delete(conversation_id)

    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(
            work_location="南山科技园",
            budget=6000,
        ),
        latest_insights=[],
    )
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(
            commute_minutes=30,
        ),
        latest_insights=[],
    )
    profile = profile_manager.update_tags(
        conversation_id,
        {
            "preference": ["两居室"],
            "commute": ["靠近地铁"],
            "lifestyle": [],
            "budget": ["预算 6000/月"],
        },
    )

    assert profile is not None
    assert profile.preference_tags["preference"] == ["两居室"]
    assert profile.preference_tags["commute"] == ["靠近地铁"]

    profile_manager.delete(conversation_id)


def test_profile_merge_reports_same_value_as_unchanged() -> None:
    conversation_id = uuid_for("profile-manager-same-value")

    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(budget=3000),
        latest_insights=[],
    )
    profile, changed = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(budget=3000),
        latest_insights=["已识别预算"],
    )

    assert profile.budget == 3000
    assert changed is False


def test_profile_merge_reports_changed_value() -> None:
    conversation_id = uuid_for("profile-manager-changed-value")

    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(budget=3000),
        latest_insights=[],
    )
    profile, changed = profile_manager.merge(
        conversation_id,
        LivingProfilePatch(budget=4000),
        latest_insights=[],
    )

    assert profile.budget == 4000
    assert changed is True
