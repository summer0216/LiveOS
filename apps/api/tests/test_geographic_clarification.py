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


def test_geographic_resolver_uses_explicit_city_to_disambiguate(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "status": "1",
                "geocodes": [
                    {
                        "formatted_address": "广东省深圳市南山区",
                        "city": "深圳市",
                        "level": "区县",
                        "location": "113.930478,22.533191",
                    },
                    {
                        "formatted_address": "黑龙江省鹤岗市南山区",
                        "city": "鹤岗市",
                        "level": "区县",
                        "location": "130.285991,47.315121",
                    },
                ],
            }

    monkeypatch.setattr("httpx.get", lambda *_args, **_kwargs: Response())

    result = geographic_resolver.resolve("深圳南山", None, "server-key")

    assert result.status == "GROUNDED"
    assert result.geographic_identity == "广东省深圳市南山区"
    assert (result.lng, result.lat) == (113.930478, 22.533191)


@pytest.mark.parametrize(
    ("identity", "formatted_address", "location"),
    [
        ("北京", "北京市", "116.407387,39.904179"),
        ("上海", "上海市", "121.473667,31.230525"),
        ("天津", "天津市", "117.200983,39.084158"),
        ("重庆", "重庆市", "106.551643,29.562849"),
    ],
)
def test_geographic_resolver_accepts_municipality_province_level(
    monkeypatch, identity: str, formatted_address: str, location: str
) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "status": "1",
                "geocodes": [
                    {
                        "formatted_address": formatted_address,
                        "city": formatted_address,
                        "level": "省",
                        "location": location,
                    }
                ],
            }

    monkeypatch.setattr("httpx.get", lambda *_args, **_kwargs: Response())

    result = geographic_resolver.resolve(identity, None, "server-key")

    assert result.status == "GROUNDED"
    assert result.geographic_identity == formatted_address
    assert result.geographic_precision == GeographicPrecision.AREA


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


def test_local_area_fallback_resolves_one_canonical_city_scoped_candidate(
    monkeypatch,
) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "status": "1",
                "pois": [
                    {
                        "name": "成都高新技术产业开发区(南区)",
                        "type": "商务住宅;产业园区;产业园区",
                        "cityname": "成都市",
                        "location": "104.065546,30.592078",
                    },
                    {
                        "name": "成都高新技术产业开发区南区A座",
                        "type": "商务住宅;产业园区;产业园区",
                        "cityname": "成都市",
                        "location": "104.047425,30.581175",
                    },
                ],
            }

    monkeypatch.setattr("httpx.get", lambda *_args, **_kwargs: Response())

    result = geographic_resolver.resolve_local_area("高新南", "成都市", "server-key")

    assert result.status == "GROUNDED"
    assert result.geographic_identity == "成都市成都高新技术产业开发区(南区)"
    assert result.geographic_precision == GeographicPrecision.AREA
    assert (result.lng, result.lat) == (104.065546, 30.592078)


def test_local_area_fallback_rejects_ambiguous_local_identity(monkeypatch) -> None:
    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "status": "1",
                "pois": [
                    {
                        "name": "甲科技园",
                        "type": "商务住宅;产业园区;产业园区",
                        "cityname": "深圳市",
                        "location": "113.8,22.7",
                    },
                    {
                        "name": "乙科技园",
                        "type": "商务住宅;产业园区;产业园区",
                        "cityname": "深圳市",
                        "location": "113.9,22.6",
                    },
                ],
            }

    monkeypatch.setattr("httpx.get", lambda *_args, **_kwargs: Response())

    result = geographic_resolver.resolve_local_area("科技园", "深圳市", "server-key")

    assert result.status == "UNRESOLVED"
    assert result.ambiguous is True
