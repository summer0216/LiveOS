import pytest

from app.models.profile import LivingProfile
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus
from app.services.geographic_resolution import GeographicResolutionResult
from app.services.profile_manager import profile_manager
from app.stores.runtime import profile_store
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


def test_legacy_work_grounding_is_replaced_by_real_resolution(monkeypatch) -> None:
    conversation_id = uuid_for("profile-manager-legacy-work-recovery")
    profile_manager.get_or_create(conversation_id)
    profile_store.save(
        conversation_id,
        LivingProfile(
            work_location="南山科技园",
            budget=6000,
            commute_minutes=30,
            geographic_identity="深圳市南山区南山科技园",
            geographic_precision=GeographicPrecision.AREA,
            geographic_status=GeographicStatus.GROUNDED,
            lng=113.947,
            lat=22.541,
        ),
    )
    monkeypatch.setattr(
        "app.services.profile_manager.geographic_resolver.resolve",
        lambda *_args: GeographicResolutionResult(
            status="GROUNDED",
            geographic_identity="广东省深圳市南山区科技园",
            geographic_precision=GeographicPrecision.AREA,
            lng=113.94604,
            lat=22.54461,
        ),
    )

    result = profile_manager.resolve_work_geographic_grounding(
        conversation_id,
        context_location=None,
        api_key="server-key",
    )
    profile = profile_manager.get(conversation_id)

    assert result.status == "GROUNDED"
    assert profile is not None
    assert profile.geographic_identity == "广东省深圳市南山区科技园"
    assert profile.geographic_status == GeographicStatus.GROUNDED
    assert profile.lng == 113.94604
    assert profile.lat == 22.54461
    assert profile.budget == 6000
    assert profile.commute_minutes == 30


def test_failed_legacy_work_recovery_does_not_preserve_fake_grounding(
    monkeypatch,
) -> None:
    conversation_id = uuid_for("profile-manager-legacy-work-failure")
    profile_manager.get_or_create(conversation_id)
    profile_store.save(
        conversation_id,
        LivingProfile(
            work_location="南山科技园",
            budget=6000,
            commute_minutes=30,
            geographic_identity="深圳市南山区南山科技园",
            geographic_precision=GeographicPrecision.AREA,
            geographic_status=GeographicStatus.GROUNDED,
            lng=113.947,
            lat=22.541,
        ),
    )
    monkeypatch.setattr(
        "app.services.profile_manager.geographic_resolver.resolve",
        lambda *_args: GeographicResolutionResult(status="UNRESOLVED"),
    )

    result = profile_manager.resolve_work_geographic_grounding(
        conversation_id,
        context_location=None,
        api_key="server-key",
    )
    profile = profile_manager.get(conversation_id)

    assert result.status == "UNRESOLVED"
    assert profile is not None
    assert profile.geographic_status == GeographicStatus.UNRESOLVED
    assert profile.geographic_identity is None
    assert profile.lng is None
    assert profile.lat is None
    assert profile.budget == 6000
    assert profile.commute_minutes == 30


def test_verified_non_legacy_work_grounding_does_not_need_resolution() -> None:
    profile = LivingProfile(
        work_location="南山科技园",
        geographic_identity="广东省深圳市南山区科技园",
        geographic_precision=GeographicPrecision.AREA,
        geographic_status=GeographicStatus.GROUNDED,
        lng=113.94604,
        lat=22.54461,
    )

    assert profile_manager.needs_work_geographic_resolution(profile) is False


def test_unresolved_explicit_city_work_does_not_use_unrelated_context(monkeypatch):
    conversation_id = uuid_for("profile-manager-explicit-city-guard")
    profile_manager.get_or_create(conversation_id)
    profile_store.save(conversation_id, LivingProfile(work_location="北京市中关村"))
    calls = []

    def resolve(title, context, key):
        calls.append((title, context))
        return GeographicResolutionResult(
            status="UNRESOLVED", geographic_identity="北京市中关村",
        )

    def unexpected_local(*args):
        pytest.fail("Explicit city must not fall through to unrelated city context")

    monkeypatch.setattr("app.services.profile_manager.geographic_resolver.resolve", resolve)
    monkeypatch.setattr(
        "app.services.profile_manager.geographic_resolver.resolve_local_area",
        unexpected_local,
    )
    result = profile_manager.resolve_work_geographic_grounding(
        conversation_id, context_location="成都市", api_key="server-key",
    )
    assert result.status == "UNRESOLVED"
    assert calls == [("北京市中关村", None)]
    profile = profile_manager.get(conversation_id)
    assert profile.lng is None and profile.lat is None


@pytest.mark.parametrize("context", [None, "北京市", "成都市"])
def test_work_grounding_uses_existing_local_area_resolution(
    monkeypatch, context,
) -> None:
    conversation_id = uuid_for("profile-manager-local-work-grounding")
    profile_manager.get_or_create(conversation_id)
    profile_store.save(
        conversation_id,
        LivingProfile(work_location="中关村"),
    )
    monkeypatch.setattr(
        "app.services.profile_manager.geographic_resolver.resolve",
        lambda *_args: GeographicResolutionResult(status="UNRESOLVED"),
    )
    calls = []

    def resolve_local(title, city, key):
        calls.append((title, city))
        return GeographicResolutionResult(
            status="GROUNDED",
            geographic_identity="北京市中关村",
            geographic_precision=GeographicPrecision.AREA,
            lng=116.321669,
            lat=39.985266,
        )

    monkeypatch.setattr(
        "app.services.profile_manager.geographic_resolver.resolve_local_area",
        resolve_local,
    )

    result = profile_manager.resolve_work_geographic_grounding(
        conversation_id,
        context_location=context,
        api_key="server-key",
    )
    profile = profile_manager.get(conversation_id)

    assert result.status == "GROUNDED"
    assert profile is not None
    assert profile.work_location == "中关村"
    assert profile.geographic_identity == "北京市中关村"
    assert profile.geographic_status == GeographicStatus.GROUNDED
    assert (profile.lng, profile.lat) == (116.321669, 39.985266)
    assert calls == [("中关村", None)]


def test_work_grounding_removes_matching_city_only_for_contextual_lookup(
    monkeypatch,
) -> None:
    conversation_id = uuid_for("profile-manager-city-qualified-local-work")
    profile_manager.get_or_create(conversation_id)
    profile_store.save(
        conversation_id,
        LivingProfile(work_location="北京的中关村"),
    )
    resolve_calls = []
    local_calls = []

    def resolve(title, context, key):
        resolve_calls.append((title, context))
        return GeographicResolutionResult(status="UNRESOLVED")

    def resolve_local(title, context, key):
        local_calls.append((title, context))
        if context == "北京市" and title == "中关村":
            return GeographicResolutionResult(
                status="GROUNDED",
                geographic_identity="北京市中关村",
                geographic_precision=GeographicPrecision.AREA,
                lng=116.321669,
                lat=39.985266,
            )
        return GeographicResolutionResult(status="UNRESOLVED")

    monkeypatch.setattr(
        "app.services.profile_manager.geographic_resolver.resolve", resolve,
    )
    monkeypatch.setattr(
        "app.services.profile_manager.geographic_resolver.resolve_local_area",
        resolve_local,
    )

    result = profile_manager.resolve_work_geographic_grounding(
        conversation_id,
        context_location="北京市",
        api_key="server-key",
    )

    assert result.status == "GROUNDED"
    assert resolve_calls == [("北京的中关村", None), ("中关村", "北京市")]
    assert local_calls == [("北京的中关村", None), ("中关村", "北京市")]
    profile = profile_manager.get(conversation_id)
    assert profile is not None
    assert profile.work_location == "北京的中关村"
    assert profile.geographic_identity == "北京市中关村"
    assert (profile.lng, profile.lat) == (116.321669, 39.985266)
