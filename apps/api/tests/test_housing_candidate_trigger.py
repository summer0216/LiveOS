from app.models.decision_geography import DecisionGeography
from app.models.profile import LivingProfile
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.geographic_resolution import GeographicResolutionResult
from app.services.housing_candidate_discovery import HousingDiscoveryResult
from app.stores.runtime import profile_store
from tests.ids import uuid_for


def grounded_housing_profile(
    *,
    budget: int | None = 6000,
    commute_minutes: int | None = 30,
    geographic_precision: GeographicPrecision = GeographicPrecision.PLACE,
) -> LivingProfile:
    return LivingProfile(
        work_location="南山科技园",
        budget=budget,
        commute_minutes=commute_minutes,
        geographic_identity="广东省深圳市南山区科技园",
        geographic_precision=geographic_precision,
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


def test_non_housing_without_budget_or_missing_commute_does_not_trigger_discovery(
    monkeypatch,
) -> None:
    conversation_id = uuid_for("housing-candidate-trigger-guard")
    conversation_manager.get_or_create(conversation_id)
    calls: list[dict] = []
    monkeypatch.setattr(
        "app.services.chat_service.housing_candidate_discovery.discover",
        lambda **kwargs: calls.append(kwargs),
    )

    profile_store.save(conversation_id, grounded_housing_profile(budget=None))
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


def test_area_work_does_not_trigger_point_to_point_discovery(monkeypatch) -> None:
    conversation_id = uuid_for("housing-candidate-area-work-guard")
    conversation_manager.get_or_create(conversation_id)
    profile_store.save(
        conversation_id,
        grounded_housing_profile(geographic_precision=GeographicPrecision.AREA),
    )
    calls: list[dict] = []
    monkeypatch.setattr(
        "app.services.chat_service.housing_candidate_discovery.discover",
        lambda **kwargs: calls.append(kwargs),
    )

    chat_service._update_profile(
        conversation_id,
        [],
        analysis=housing_analysis(),
        apply_decision_geography=False,
        current_decision_geography=housing_analysis().decision_geography,
    )

    assert calls == []


def test_place_refinement_with_persisted_housing_constraints_triggers(monkeypatch):
    conversation_id = uuid_for("housing-work-refinement-constraints")
    conversation_manager.get_or_create(conversation_id)
    profile_store.save(conversation_id, grounded_housing_profile())
    calls = []
    monkeypatch.setattr(
        "app.services.chat_service.housing_candidate_discovery.discover",
        lambda **kwargs: calls.append(kwargs) or HousingDiscoveryResult(0, 0, 0, ()),
    )
    chat_service._update_profile(
        conversation_id, [], analysis=housing_analysis("work_location"),
        apply_decision_geography=False,
        current_decision_geography=housing_analysis("work_location").decision_geography,
    )
    assert len(calls) == 1
    assert calls[0]["commute_limit_minutes"] == 30


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


def test_full_housing_analysis_triggers_discovery_without_early_geography(
    monkeypatch,
) -> None:
    conversation_id = uuid_for("housing-candidate-trigger-full-analysis")
    conversation_manager.get_or_create(conversation_id)
    profile_store.save(conversation_id, grounded_housing_profile())
    calls: list[dict] = []
    monkeypatch.setattr(
        "app.services.chat_service.housing_candidate_discovery.discover",
        lambda **kwargs: calls.append(kwargs)
        or HousingDiscoveryResult(20, 16, 4, ()),
    )

    chat_service._update_profile(
        conversation_id,
        [],
        analysis=housing_analysis(),
        apply_decision_geography=False,
        current_decision_geography=None,
    )

    assert len(calls) == 1
    assert calls[0]["conversation_id"] == conversation_id


def test_active_decision_city_owns_work_grounding_context(monkeypatch) -> None:
    conversation_id = uuid_for("active-decision-city-work-context")
    conversation_manager.get_or_create(conversation_id)
    profile_store.save(
        conversation_id,
        LivingProfile(
            work_location="浦东新区",
            budget=3000,
            commute_minutes=None,
            preferred_city="杭州",
        ),
    )
    decision_geography = DecisionGeography(
        intent_established=True,
        intent_type="housing",
        identity="浦东新区",
        identity_source="USER",
        status="GROUNDED",
        lng=121.5447,
        lat=31.2215,
    )
    contexts: list[str | None] = []
    monkeypatch.setattr(
        "app.services.chat_service.decision_geography_service.city_context",
        lambda state, _api_key: "上海市" if state == decision_geography else None,
    )
    monkeypatch.setattr(
        "app.services.chat_service.profile_manager.resolve_work_geographic_grounding",
        lambda _conversation_id, *, context_location, api_key: (
            contexts.append(context_location)
            or GeographicResolutionResult(status="UNRESOLVED")
        ),
    )

    chat_service._update_profile(
        conversation_id,
        [],
        analysis=ProfileAnalysis(patch=LivingProfilePatch()),
        apply_decision_geography=False,
        current_decision_geography=decision_geography,
    )

    assert contexts == ["上海市"]


def test_active_decision_region_does_not_fall_back_to_stale_profile_city(
    monkeypatch,
) -> None:
    conversation_id = uuid_for("active-decision-region-work-context")
    conversation_manager.get_or_create(conversation_id)
    profile_store.save(
        conversation_id,
        LivingProfile(
            work_location="福建",
            budget=3000,
            commute_minutes=None,
            preferred_city="成都",
        ),
    )
    decision_geography = DecisionGeography(
        intent_established=True,
        intent_type="relocate_for_work",
        identity="福建省",
        identity_source="USER",
        geographic_scope="REGION",
        status="GROUNDED",
        lng=119.295144,
        lat=26.100779,
    )
    contexts: list[str | None] = []
    monkeypatch.setattr(
        "app.services.chat_service.decision_geography_service.city_context",
        lambda state, _api_key: None if state == decision_geography else "成都",
    )
    monkeypatch.setattr(
        "app.services.chat_service.profile_manager.resolve_work_geographic_grounding",
        lambda _conversation_id, *, context_location, api_key: (
            contexts.append(context_location)
            or GeographicResolutionResult(status="UNRESOLVED")
        ),
    )

    chat_service._update_profile(
        conversation_id,
        [],
        analysis=ProfileAnalysis(patch=LivingProfilePatch()),
        apply_decision_geography=False,
        current_decision_geography=decision_geography,
    )

    assert contexts == [None]
