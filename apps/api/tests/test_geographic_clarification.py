import json
from types import SimpleNamespace

import pytest

from app.models.geographic_clarification import GeographicClarification
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus, Property
from app.services.chat_service import chat_service
from app.services.geographic_resolution import geographic_resolver
from app.services.profile_intelligence import profile_intelligence
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager


def test_geographic_clarification_requires_complete_grounding() -> None:
    with pytest.raises(ValueError):
        GeographicClarification(
            relevant=True,
            target_property_id="property-a",
            geographic_identity="科苑花园",
            geographic_precision=GeographicPrecision.PLACE,
        )


def test_profile_intelligence_extracts_grounding_result() -> None:
    analysis = profile_intelligence._build_analysis(
        json.dumps(
            {
                "geographic_clarification": {
                    "relevant": True,
                    "target_property_id": "property-a",
                    "geographic_identity": "科苑花园",
                    "geographic_precision": "PLACE",
                    "lng": 113.92,
                    "lat": 22.52,
                }
            }
        ),
        "A 的地址是科苑花园。",
    )

    assert analysis.geographic_clarification.relevant is True
    assert analysis.geographic_clarification.target_property_id == "property-a"
    assert analysis.geographic_clarification.geographic_precision == (
        GeographicPrecision.PLACE
    )


def test_invalid_grounding_result_is_ignored() -> None:
    analysis = profile_intelligence._build_analysis(
        json.dumps(
            {
                "geographic_clarification": {
                    "relevant": True,
                    "target_property_id": "property-a",
                    "geographic_identity": "科苑花园",
                    "geographic_precision": "PLACE",
                    "lng": None,
                    "lat": None,
                }
            }
        ),
        "A 的地址还不确定。",
    )

    assert analysis.geographic_clarification.relevant is False


def test_chat_flow_persists_geographic_clarification(monkeypatch) -> None:
    property_ = Property(
        id="property-a",
        conversation_id="conversation-a",
        title="科苑花园",
    )
    clarification = GeographicClarification(
        relevant=True,
        target_property_id=property_.id,
        geographic_identity="科苑花园",
        geographic_precision=GeographicPrecision.PLACE,
        lng=113.92,
        lat=22.52,
    )
    analysis = ProfileAnalysis(
        patch=LivingProfilePatch(),
        geographic_clarification=clarification,
    )
    updates: list[dict] = []

    monkeypatch.setattr(property_manager, "list", lambda _conversation_id: [property_])
    monkeypatch.setattr(
        profile_intelligence,
        "analyze",
        lambda _history, _properties: analysis,
    )
    monkeypatch.setattr(
        profile_manager,
        "merge",
        lambda **_kwargs: SimpleNamespace(changed=False, causes=()),
    )
    monkeypatch.setattr(
        property_manager,
        "update_geographic_grounding",
        lambda property_id, conversation_id, **kwargs: updates.append(
            {
                "property_id": property_id,
                "conversation_id": conversation_id,
                **kwargs,
            }
        ),
    )

    chat_service._update_profile("conversation-a", [])

    assert updates == [
        {
            "property_id": "property-a",
            "conversation_id": "conversation-a",
            "geographic_identity": "科苑花园",
            "geographic_precision": GeographicPrecision.PLACE,
            "geographic_status": GeographicStatus.GROUNDED,
            "lng": 113.92,
            "lat": 22.52,
        }
    ]


def test_geographic_resolver_requires_server_key() -> None:
    result = geographic_resolver.resolve("后海公寓", "深圳市南山区", None)

    assert result.status == "UNRESOLVED"


def test_geographic_resolver_rejects_ambiguous_result(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"status": "1", "geocodes": [{}, {}]}

    monkeypatch.setattr("httpx.get", lambda *_args, **_kwargs: Response())

    result = geographic_resolver.resolve("后海公寓", "深圳市南山区", "server-key")

    assert result.status == "UNRESOLVED"
    assert result.ambiguous is True


def test_geographic_resolver_rejects_shortened_identity(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "status": "1",
                "geocodes": [
                    {
                        "formatted_address": "广东省深圳市南山区西丽",
                        "level": "兴趣点",
                        "location": "113.943867,22.568801",
                    }
                ],
            }

    monkeypatch.setattr("httpx.get", lambda *_args, **_kwargs: Response())

    result = geographic_resolver.resolve("西丽居", "深圳市南山区", "server-key")

    assert result.status == "UNRESOLVED"
