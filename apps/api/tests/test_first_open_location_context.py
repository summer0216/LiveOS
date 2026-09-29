from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus, Property
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.geographic_resolution import (
    CurrentGeographicContext,
    GeographicResolutionResult,
    geographic_resolver,
)
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from tests.ids import uuid_for


def test_browser_coordinates_resolve_complete_local_context(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "status": "1",
                "regeocode": {
                    "addressComponent": {
                        "province": "四川省",
                        "city": "成都市",
                        "district": "郫都区",
                    },
                },
            }

    monkeypatch.setattr("httpx.get", lambda *_args, **_kwargs: Response())

    context = geographic_resolver.resolve_current_context(
        103.920730,
        30.753792,
        "server-key",
    )

    assert context == CurrentGeographicContext("四川省", "成都市", "郫都区")
    assert context.grounding_context == "四川省成都市郫都区"


def test_first_open_context_grounds_matching_ambiguous_place_without_persisting_it(
    monkeypatch,
) -> None:
    conversation_id = uuid_for("first-open-context-matching-place")
    conversation_manager.get_or_create(conversation_id)
    contexts: list[str | None] = []

    monkeypatch.setattr(
        geographic_resolver,
        "resolve_current_context",
        lambda *_args: CurrentGeographicContext("四川省", "成都市", "郫都区"),
    )

    def resolve(title: str, context: str | None, _api_key: str | None):
        contexts.append(context)
        assert title == "龙湖时代天街"
        if context == "四川省成都市郫都区":
            return GeographicResolutionResult(
                status="GROUNDED",
                geographic_identity="四川省成都市郫都区龙湖·时代天街",
                geographic_precision=GeographicPrecision.PLACE,
                lng=103.920730,
                lat=30.753792,
            )
        return GeographicResolutionResult(status="UNRESOLVED", ambiguous=True)

    monkeypatch.setattr(geographic_resolver, "resolve", resolve)

    chat_service._update_profile(
        conversation_id,
        [],
        current_geographic_reality=(104.0668, 30.5728),
        analysis=ProfileAnalysis(
            patch=LivingProfilePatch(),
            choices=[Property(title="龙湖时代天街")],
        ),
        apply_decision_geography=False,
    )

    stored = property_manager.list(conversation_id)
    profile = profile_manager.get(conversation_id)
    assert contexts == ["四川省成都市郫都区"]
    assert len(stored) == 1
    assert stored[0].geographic_status == GeographicStatus.GROUNDED
    assert stored[0].geographic_identity == "四川省成都市郫都区龙湖·时代天街"
    assert (stored[0].lng, stored[0].lat) == (103.920730, 30.753792)
    assert stored[0].district is None
    assert profile is not None
    assert profile.preferred_city is None
    assert profile.geographic_identity is None


def test_insufficient_first_open_context_preserves_unresolved_clarification_path(
    monkeypatch,
) -> None:
    conversation_id = uuid_for("first-open-context-insufficient")
    conversation_manager.get_or_create(conversation_id)
    contexts: list[str | None] = []
    monkeypatch.setattr(
        geographic_resolver,
        "resolve_current_context",
        lambda *_args: None,
    )
    monkeypatch.setattr(
        geographic_resolver,
        "resolve",
        lambda _title, context, _api_key: (
            contexts.append(context)
            or GeographicResolutionResult(status="UNRESOLVED", ambiguous=True)
        ),
    )

    chat_service._update_profile(
        conversation_id,
        [],
        current_geographic_reality=(104.0668, 30.5728),
        analysis=ProfileAnalysis(
            patch=LivingProfilePatch(),
            choices=[Property(title="龙湖时代天街")],
        ),
        apply_decision_geography=False,
    )

    stored = property_manager.list(conversation_id)
    assert contexts == [None]
    assert len(stored) == 1
    assert stored[0].geographic_status == GeographicStatus.UNRESOLVED
    assert stored[0].geographic_identity is None
