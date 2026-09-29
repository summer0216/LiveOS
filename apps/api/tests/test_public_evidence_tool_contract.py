import json
from types import SimpleNamespace

import pytest

from app.core.ai_client import AIClient
from app.services.external_rent_reality_service import PUBLIC_RENT_TOOL


class _Completions:
    def __init__(self, arguments: str) -> None:
        self.arguments = arguments
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            function = SimpleNamespace(
                name="search_public_rental_evidence", arguments=self.arguments,
            )
            message = SimpleNamespace(
                content=None,
                tool_calls=[SimpleNamespace(id="call-1", function=function)],
            )
        else:
            message = SimpleNamespace(content='{"done": true}', tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class _Client:
    def __init__(self, arguments: str) -> None:
        self.chat = SimpleNamespace(completions=_Completions(arguments))

    def with_options(self, **_kwargs):
        return self


def _intelligence(arguments: str) -> AIClient:
    intelligence = AIClient()
    intelligence.client = _Client(arguments)
    return intelligence


def test_expected_public_rental_tool_arguments_validate_and_dispatch_once():
    arguments = {
        "property_name": "龙湖时代天街",
        "city": "成都市",
        "district": "郫都区",
        "lng": 103.92073,
        "lat": 30.753792,
    }
    dispatched = []
    intelligence = _intelligence(json.dumps(arguments, ensure_ascii=False))

    result = intelligence.generate_json_with_public_evidence_tool(
        "search", tool=PUBLIC_RENT_TOOL,
        dispatch=lambda actual: dispatched.append(actual) or '{"evidence": []}',
    )

    assert result == '{"done": true}'
    assert dispatched == [arguments]
    assert intelligence.client.chat.completions.calls[0]["max_tokens"] == 512


@pytest.mark.parametrize(
    "arguments",
    [
        '{"property_name": "龙湖时代天街", "lng"',
        '[{"property_name": "龙湖时代天街"}]',
        '{"property_name": "龙湖时代天街", "unexpected": true}',
        '{"property_name": "龙湖时代天街", "lng": "103.92073"}',
    ],
)
def test_invalid_public_rental_tool_arguments_remain_rejected(arguments):
    dispatched = []

    with pytest.raises((RuntimeError, TypeError), match="invalid tool arguments"):
        _intelligence(arguments).generate_json_with_public_evidence_tool(
            "search", tool=PUBLIC_RENT_TOOL,
            dispatch=lambda actual: dispatched.append(actual) or '{}',
        )

    assert dispatched == []
