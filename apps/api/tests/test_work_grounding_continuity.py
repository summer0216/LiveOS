from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_geography_service import decision_geography_service
from app.services.geographic_resolution import GeographicResolutionResult
from app.services.profile_manager import profile_manager
from tests.ids import uuid_for


def _grounded_result() -> GeographicResolutionResult:
    return GeographicResolutionResult(
        status="GROUNDED",
        geographic_identity="北京市海淀区中关村",
        geographic_precision=GeographicPrecision.AREA,
        geographic_scope="LOCAL",
        lng=116.321669,
        lat=39.985266,
    )


def test_explicit_work_decision_grounding_continues_into_profile(monkeypatch) -> None:
    conversation_id = uuid_for("work-decision-grounding-continuity")
    conversation_manager.get_or_create(conversation_id)
    calls: list[tuple[str, str | None]] = []

    def resolve(identity: str, context: str | None, _api_key: str | None):
        calls.append((identity, context))
        return _grounded_result()

    monkeypatch.setattr(
        "app.services.decision_geography_service.geographic_resolver.resolve",
        resolve,
    )
    monkeypatch.setattr(
        "app.services.decision_geography_service.geographic_resolver.resolve_city_context",
        lambda *_args: "北京市",
    )

    chat_service._update_profile(
        conversation_id,
        [],
        analysis=ProfileAnalysis(
            patch=LivingProfilePatch(),
            decision_geography={
                "intent_established": True,
                "intent_type": "work",
                "identity": "北京的中关村",
                "identity_source": "USER",
            },
        ),
    )

    decision_geography = decision_geography_service.get(conversation_id)
    profile = profile_manager.get(conversation_id)

    assert calls == [("北京的中关村", None)]
    assert decision_geography is not None
    assert decision_geography.status == GeographicStatus.GROUNDED.value
    assert decision_geography.geographic_identity == "北京市海淀区中关村"
    assert decision_geography.geographic_precision == GeographicPrecision.AREA
    assert (decision_geography.lng, decision_geography.lat) == (
        116.321669,
        39.985266,
    )
    assert profile is not None
    assert profile.work_location == "北京的中关村"
    assert profile.geographic_identity == decision_geography.geographic_identity
    assert profile.geographic_precision == GeographicPrecision.AREA
    assert profile.geographic_status == GeographicStatus.GROUNDED
    assert (profile.lng, profile.lat) == (
        decision_geography.lng,
        decision_geography.lat,
    )


def test_residence_decision_grounding_does_not_become_profile_work(monkeypatch) -> None:
    conversation_id = uuid_for("residence-decision-is-not-profile-work")
    conversation_manager.get_or_create(conversation_id)
    monkeypatch.setattr(
        "app.services.decision_geography_service.geographic_resolver.resolve",
        lambda *_args: _grounded_result(),
    )
    monkeypatch.setattr(
        "app.services.decision_geography_service.geographic_resolver.resolve_city_context",
        lambda *_args: "北京市",
    )

    chat_service._update_profile(
        conversation_id,
        [],
        analysis=ProfileAnalysis(
            patch=LivingProfilePatch(),
            decision_geography={
                "intent_established": True,
                "intent_type": "housing",
                "identity": "北京的中关村",
                "identity_source": "USER",
            },
        ),
    )

    profile = profile_manager.get(conversation_id)
    assert profile is not None
    assert profile.work_location is None
    assert profile.geographic_status == GeographicStatus.UNRESOLVED
    assert profile.geographic_identity is None
    assert profile.geographic_precision is None
    assert profile.lng is None
    assert profile.lat is None
