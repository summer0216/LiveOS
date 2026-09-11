from app.models.decision_geography import DecisionGeography
from app.models.profile import LivingProfile
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.housing_candidate_discovery import HousingDiscoveryResult
from app.stores.runtime import profile_store
from tests.ids import uuid_for


def grounded_housing_profile(*, commute_minutes: int | None = 30) -> LivingProfile:
    return LivingProfile(
        work_location="南山科技园",
        budget=6000,
        commute_minutes=commute_minutes,
        geographic_identity="广东省深圳市南山区科技园",
        geographic_precision=GeographicPrecision.AREA,
        geographic_status=GeographicStatus.GROUNDED,
        lng=113.94604,
        lat=22.54461,
    )


def housing_analysis(intent_type: str = "housing_search") -> ProfileAnalysis:
    return ProfileAnalysis(
        patch=LivingProfilePatch(),
        decision_geography=DecisionGeography(
            intent_established=True,
            intent_type=intent_type,
            identity="南山科技园",
            identity_source="USER",
        ),
    )


def test_grounded_housing_context_triggers_candidate_discovery(monkeypatch) -> None:
    conversation_id = uuid_for("housing-candidate-trigger")
    conversation_manager.get_or_create(conversation_id)
    profile_store.save(conversation_id, grounded_housing_profile())
    calls: list[dict] = []

    def discover(**kwargs) -> HousingDiscoveryResult:
        calls.append(kwargs)
        return HousingDiscoveryResult(20, 16, 4, ())

    monkeypatch.setattr(
        "app.services.chat_service.housing_candidate_discovery.discover",
        discover,
    )

    chat_service._update_profile(
        conversation_id,
        [],
        analysis=housing_analysis(),
        apply_decision_geography=False,
        current_decision_geography=housing_analysis().decision_geography,
    )

    assert calls == [
        {
            "conversation_id": conversation_id,
            "work_lng": 113.94604,
            "work_lat": 22.54461,
            "commute_limit_minutes": 30,
            "api_key": calls[0]["api_key"],
        }
    ]


def test_non_housing_or_missing_commute_does_not_trigger_discovery(
    monkeypatch,
) -> None:
    conversation_id = uuid_for("housing-candidate-trigger-guard")
    conversation_manager.get_or_create(conversation_id)
    calls: list[dict] = []
    monkeypatch.setattr(
        "app.services.chat_service.housing_candidate_discovery.discover",
        lambda **kwargs: calls.append(kwargs),
    )

    profile_store.save(conversation_id, grounded_housing_profile())
    chat_service._update_profile(
        conversation_id,
        [],
        analysis=housing_analysis("RELOCATE_FOR_WORK"),
        apply_decision_geography=False,
        current_decision_geography=housing_analysis(
            "RELOCATE_FOR_WORK"
        ).decision_geography,
    )

    profile_store.save(
        conversation_id,
        grounded_housing_profile(commute_minutes=None),
    )
    chat_service._update_profile(
        conversation_id,
        [],
        analysis=housing_analysis(),
        apply_decision_geography=False,
        current_decision_geography=housing_analysis().decision_geography,
    )

    assert calls == []


def test_stream_path_schedules_discovery_without_blocking_profile_update(
    monkeypatch,
) -> None:
    conversation_id = uuid_for("housing-candidate-trigger-scheduled")
    conversation_manager.get_or_create(conversation_id)
    profile_store.save(conversation_id, grounded_housing_profile())
    discovery_calls: list[dict] = []
    scheduled: list[object] = []

    monkeypatch.setattr(
        "app.services.chat_service.housing_candidate_discovery.discover",
        lambda **kwargs: discovery_calls.append(kwargs)
        or HousingDiscoveryResult(20, 16, 4, ()),
    )

    chat_service._update_profile(
        conversation_id,
        [],
        analysis=housing_analysis(),
        apply_decision_geography=False,
        current_decision_geography=housing_analysis().decision_geography,
        schedule_housing_discovery=scheduled.append,
    )

    assert discovery_calls == []
    assert len(scheduled) == 1

    task = scheduled[0]
    assert callable(task)
    task()

    assert len(discovery_calls) == 1
