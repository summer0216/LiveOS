import json
from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.ai_client import ai_client
from app.main import app
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.services.decision_service import decision_service
from app.services.decision_record_service import decision_record_service
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager

client = TestClient(app)

CONVERSATION_IDS = (
    "decision-no-profile",
    "decision-no-property",
    "decision-single",
    "decision-multiple",
    "decision-isolation-a",
    "decision-isolation-b",
    "decision-invalid-id",
    "decision-invalid-confidence",
    "decision-invalid-json",
    "decision-ai-error",
)


@pytest.fixture(autouse=True)
def clean_decision_data() -> Iterator[None]:
    for conversation_id in CONVERSATION_IDS:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)

    yield

    for conversation_id in CONVERSATION_IDS:
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)
        decision_record_service.delete_conversation(conversation_id)


def create_profile(conversation_id: str) -> None:
    profile_manager.merge(
        conversation_id=conversation_id,
        patch=LivingProfilePatch(
            work_location="南山科技园",
            budget=6000,
            commute_minutes=30,
            preferred_city="深圳",
            family_size=2,
            has_pet=False,
        ),
        latest_insights=[],
    )


def create_property(
    conversation_id: str,
    title: str,
    *,
    rent: int = 5800,
    commute_minutes: int = 25,
) -> Property:
    return property_manager.create(
        conversation_id=conversation_id,
        property_=Property(
            title=title,
            district="南山",
            rent=rent,
            area=65,
            bedrooms=2,
            bathrooms=1,
            commute_minutes=commute_minutes,
            pet_friendly=True,
        ),
    )


def ready_json(
    property_id: str,
    *,
    confidence: float = 0.82,
) -> str:
    return json.dumps(
        {
            "status": "ready",
            "summary": "当前候选房源符合已知的预算与通勤要求。",
            "best_property_id": property_id,
            "reasons": [
                {
                    "title": "预算匹配",
                    "description": "已提供的租金处于当前预算范围内。",
                },
            ],
            "trade_offs": [],
            "confidence": confidence,
        },
        ensure_ascii=False,
    )


def set_json_response(
    monkeypatch: pytest.MonkeyPatch,
    response: str | Callable[[str], str],
) -> None:
    generator = response if callable(response) else lambda _prompt: response
    monkeypatch.setattr(ai_client, "generate_json", generator)


def test_waiting_without_profile_does_not_call_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_call(_prompt: str) -> str:
        raise AssertionError("AI must not be called without a profile.")

    set_json_response(monkeypatch, unexpected_call)

    response = client.get(
        "/api/decisions",
        params={"conversation_id": "decision-no-profile"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "waiting"
    assert response.json()["best_property_id"] is None


def test_waiting_without_property_does_not_call_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_profile("decision-no-property")

    def unexpected_call(_prompt: str) -> str:
        raise AssertionError("AI must not be called without a property.")

    set_json_response(monkeypatch, unexpected_call)

    result = decision_service.generate("decision-no-property")

    assert result.status == "waiting"
    assert result.best_property_id is None


def test_single_property_returns_real_id_and_single_candidate_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = "decision-single"
    create_profile(conversation_id)
    property_ = create_property(conversation_id, "唯一候选")
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        assert property_.id is not None
        return ready_json(property_.id)

    set_json_response(monkeypatch, generate)

    response = client.get(
        "/api/decisions",
        params={"conversation_id": conversation_id},
    )
    result = response.json()

    assert response.status_code == 200
    assert result["status"] == "ready"
    assert result["best_property_id"] == property_.id
    assert "There is one candidate" in prompts[0]
    assert "multiple properties were compared" in prompts[0]


def test_multiple_properties_returns_one_real_property(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = "decision-multiple"
    create_profile(conversation_id)
    first = create_property(conversation_id, "候选一")
    second = create_property(
        conversation_id,
        "候选二",
        rent=6200,
        commute_minutes=20,
    )
    assert first.id is not None
    assert second.id is not None
    set_json_response(monkeypatch, ready_json(second.id))

    result = decision_service.generate(conversation_id)

    assert result.status == "ready"
    assert result.best_property_id == second.id
    assert result.best_property_id in {first.id, second.id}


def test_conversation_decisions_cannot_reference_other_properties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_a = "decision-isolation-a"
    conversation_b = "decision-isolation-b"
    create_profile(conversation_a)
    create_profile(conversation_b)
    property_a = create_property(conversation_a, "A 房源")
    property_b = create_property(conversation_b, "B 房源")
    assert property_a.id is not None
    assert property_b.id is not None
    set_json_response(monkeypatch, ready_json(property_b.id))

    result_a = decision_service.generate(conversation_a)

    assert result_a.status == "waiting"
    assert result_a.best_property_id is None

    set_json_response(monkeypatch, ready_json(property_a.id))
    result_b = decision_service.generate(conversation_b)

    assert result_b.status == "waiting"
    assert result_b.best_property_id is None


def test_unknown_property_id_degrades_to_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = "decision-invalid-id"
    create_profile(conversation_id)
    create_property(conversation_id, "真实房源")
    set_json_response(monkeypatch, ready_json("unknown-property"))

    result = decision_service.generate(conversation_id)

    assert result.status == "waiting"
    assert result.best_property_id is None


def test_invalid_confidence_degrades_to_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = "decision-invalid-confidence"
    create_profile(conversation_id)
    property_ = create_property(conversation_id, "置信度测试")
    assert property_.id is not None
    set_json_response(
        monkeypatch,
        ready_json(property_.id, confidence=1.4),
    )

    result = decision_service.generate(conversation_id)

    assert result.status == "waiting"
    assert result.confidence is None


def test_non_json_response_degrades_to_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = "decision-invalid-json"
    create_profile(conversation_id)
    create_property(conversation_id, "JSON 测试")
    set_json_response(monkeypatch, "not JSON")

    result = decision_service.generate(conversation_id)

    assert result.status == "waiting"
    assert result.best_property_id is None


def test_ai_error_degrades_to_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = "decision-ai-error"
    create_profile(conversation_id)
    create_property(conversation_id, "异常测试")

    def raise_ai_error(_prompt: str) -> str:
        raise RuntimeError("AI unavailable")

    set_json_response(monkeypatch, raise_ai_error)

    result = decision_service.generate(conversation_id)

    assert result.status == "waiting"
    assert result.best_property_id is None
