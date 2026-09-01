import json
from collections.abc import Callable, Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.core.ai_client import ai_client
from app.main import app
from app.models.action_progress import (
    ActionProgressStatus,
    ActionProgressUpdate,
    VerificationEvidence,
    VerificationOutcomeStatus,
    VerificationOutcomeUpdate,
)
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.schemas.decision import DecisionReason, DecisionResult
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_action_progress import decision_action_progress_service
from app.services.decision_change import decision_change_context
from app.services.decision_memory_service import decision_memory_service
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.profile_intelligence import profile_intelligence
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.stores.decision_memory_store import decision_memory_store
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation

client = TestClient(app)

CONVERSATION_IDS = (
    uuid_for("decision-no-profile"),
    uuid_for("decision-no-property"),
    uuid_for("decision-grounded-waiting"),
    uuid_for("decision-verification-redecision-gap"),
    uuid_for("decision-single"),
    uuid_for("decision-multiple"),
    uuid_for("decision-isolation-a"),
    uuid_for("decision-isolation-b"),
    uuid_for("decision-invalid-id"),
    uuid_for("decision-invalid-confidence"),
    uuid_for("decision-invalid-json"),
    uuid_for("decision-ai-error"),
)


@pytest.fixture(autouse=True)
def clean_decision_data() -> Iterator[None]:
    for conversation_id in CONVERSATION_IDS:
        create_owned_conversation(client, conversation_id)
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
            "decision_gap": "该房源的实际租金与通勤是否符合预期。",
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

    create_owned_conversation(client, uuid_for("decision-no-profile"))
    response = client.get(
        "/api/decisions",
        params={"conversation_id": uuid_for("decision-no-profile")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "waiting"
    assert response.json()["best_property_id"] is None


def test_waiting_without_property_does_not_call_ai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_profile(uuid_for("decision-no-property"))

    def unexpected_call(_prompt: str) -> str:
        raise AssertionError("AI must not be called without a property.")

    set_json_response(monkeypatch, unexpected_call)

    result = decision_service.generate(uuid_for("decision-no-property"))

    assert result.status == "waiting"
    assert result.best_property_id is None


def test_grounded_waiting_returns_valid_response_without_ready_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-grounded-waiting")
    profile_manager.merge(
        conversation_id=conversation_id,
        patch=LivingProfilePatch(
            work_location="成都高新区合作路",
            budget=2200,
            commute_minutes=30,
            preferred_city="成都",
            family_size=1,
            has_pet=False,
        ),
        latest_insights=[],
    )
    create_property(conversation_id, "合作路候选", rent=2100)
    set_json_response(
        monkeypatch,
        json.dumps(
            {
                "status": "waiting",
                "summary": "实测通勤已否定当前行动，需要先形成新的候选范围。",
                "best_property_id": None,
                "reasons": [],
                "trade_offs": [],
                "confidence": None,
                "decision_gap": None,
            },
            ensure_ascii=False,
        ),
    )

    response = client.get(
        "/api/decisions",
        params={"conversation_id": conversation_id},
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "waiting",
        "summary": "实测通勤已否定当前行动，需要先形成新的候选范围。",
        "best_property_id": None,
        "reasons": [],
        "trade_offs": [],
        "confidence": None,
        "decision_gap": None,
    }
    assert decision_record_service.list(conversation_id) == []


def test_verification_redecision_persists_new_gap_and_isolates_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-verification-redecision-gap")
    create_profile(conversation_id)
    property_ = create_property(conversation_id, "通勤反馈候选")
    assert property_.id is not None
    first_record = decision_record_service.save(
        conversation_id,
        DecisionResult(
            status="ready",
            summary=(
                "当前房源可以继续考虑。"
                "下一步：在工作日高峰实测一次门到门通勤。"
            ),
            best_property_id=property_.id,
            reasons=[DecisionReason(title="当前判断", description="通勤预估可接受。")],
            confidence=0.8,
            decision_gap="工作日高峰门到门通勤是否符合当前预估。",
        ),
    )
    first_action = decision_action_progress_service.reconcile_ready_record(
        first_record
    )
    assert first_action is not None
    decision_action_progress_service.apply_update(
        conversation_id,
        ActionProgressUpdate(
            relevant=True,
            status=ActionProgressStatus.COMPLETED,
        ),
        VerificationOutcomeUpdate(
            relevant=True,
            status=VerificationOutcomeStatus.DISCONFIRMED,
            evidence=(
                VerificationEvidence(
                    field="commute_minutes",
                    value="80分钟",
                    statement="工作日高峰实测门到门约80分钟，无法接受。",
                ),
            ),
        ),
    )
    verified_before = decision_action_progress_service.latest_verified_state(
        conversation_id
    )
    assert verified_before is not None
    learning = decision_memory_service.upsert_verification_learning(
        verified_before
    )
    assert learning is not None
    calls = 0

    def generate(_prompt: str) -> str:
        nonlocal calls
        calls += 1
        return json.dumps(
            {
                "status": "ready",
                "summary": "实测通勤否定了当前行动，应调整候选区域。",
                "best_property_id": property_.id,
                "reasons": [
                    {
                        "title": "实测通勤",
                        "description": "80分钟通勤超出当前接受范围。",
                    }
                ],
                "trade_offs": [],
                "confidence": 0.8,
                "decision_gap": "新的候选区域能否满足工作日30分钟通勤要求。",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(ai_client, "generate_json", generate)

    try:
        result = decision_service.generate(conversation_id)
        current = decision_action_progress_service.current_state(conversation_id)
        verified_after = decision_action_progress_service.latest_verified_state(
            conversation_id
        )
        records = [
            record
            for record in decision_record_service.list(conversation_id)
            if record.conversation_id == conversation_id
        ]

        assert calls == 1
        assert result.status == "ready"
        assert result.decision_gap == (
            "新的候选区域能否满足工作日30分钟通勤要求。"
        )
        assert result.summary is not None
        assert result.summary.count("下一步：") == 1
        assert "新的候选区域" in result.summary
        assert len(records) == 2
        assert current is not None
        assert current.id != first_action.action_id
        assert current.status is None
        assert current.outcome_status is None
        assert verified_after == verified_before
        assert learning.source_action_id == UUID(verified_before.action_id)
    finally:
        decision_action_progress_service.delete_conversation(conversation_id)
        decision_memory_store.replace_conversation(conversation_id, [])


def test_preference_gap_ready_survives_contradicted_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-verification-redecision-gap")
    create_profile(conversation_id)
    property_ = create_property(conversation_id, "已被实测削弱的候选")
    assert property_.id is not None
    first_record = decision_record_service.save(
        conversation_id,
        DecisionResult(
            status="ready",
            summary="当前候选可以继续考虑。下一步：实测一次工作日高峰通勤。",
            best_property_id=property_.id,
            reasons=[DecisionReason(title="当前判断", description="通勤预估可接受。")],
            decision_gap="工作日高峰门到门通勤是否符合当前预估。",
        ),
    )
    decision_action_progress_service.reconcile_ready_record(first_record)
    decision_action_progress_service.apply_update(
        conversation_id,
        ActionProgressUpdate(relevant=True, status=ActionProgressStatus.COMPLETED),
        VerificationOutcomeUpdate(
            relevant=True,
            status=VerificationOutcomeStatus.DISCONFIRMED,
            evidence=(
                VerificationEvidence(
                    field="commute_minutes",
                    value="80分钟",
                    statement="工作日高峰实测门到门约80分钟，无法接受。",
                ),
            ),
        ),
    )
    preference_message = (
        "我现在不确定应该更看重更短通勤，还是更舒适的居住空间；"
        "如果每天多30分钟通勤能换来更大空间，我也还没想清楚是否值得。"
    )

    analyses = []

    def analyze(history: list[object]):
        latest_message = history[-1]
        assert latest_message.content == preference_message
        analysis = profile_intelligence._build_analysis(
            "{}",
            latest_message.content,
        )
        analyses.append(analysis)
        return analysis

    monkeypatch.setattr(profile_intelligence, "analyze", analyze)
    conversation_manager.append_user_message(conversation_id, preference_message)
    chat_service._update_profile(
        conversation_id,
        conversation_manager.get_history(conversation_id),
    )
    assert analyses[0].decision_challenge.relevant
    assert analyses[0].action_progress_update.relevant is False
    prompts: list[str] = []

    def generate(prompt: str) -> str:
        prompts.append(prompt)
        return json.dumps(
            {
                "status": "ready",
                "summary": "当前候选的实测通勤不适合继续优先考虑。",
                "best_property_id": property_.id,
                "reasons": [
                    {
                        "title": "实测通勤",
                        "description": "80分钟通勤超出当前接受范围。",
                    }
                ],
                "trade_offs": [
                    {
                        "title": "通勤与居住空间",
                        "description": "需要在更短通勤与更舒适居住空间之间确定长期优先级。",
                    }
                ],
                "confidence": 0.7,
                "decision_gap": "你尚未形成更短通勤与更舒适居住空间之间的个人取舍。",
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(ai_client, "generate_json", generate)

    try:
        result = decision_service.generate(conversation_id)

        assert result.status == "ready"
        assert result.decision_gap is not None
        assert "个人取舍" in result.decision_gap
        assert result.summary is not None
        assert result.summary.count("下一步：") == 1
        assert "二选一取舍" in result.summary
        assert "更难接受" in result.summary
        assert len(prompts) == 1
        assert preference_message in prompts[0]
        assert "current verification has weakened a" in prompts[0]
        assert "make NEXT clarify or test the user's" in prompts[0]
    finally:
        decision_action_progress_service.delete_conversation(conversation_id)
        decision_change_context.clear(conversation_id)


def test_single_property_returns_real_id_and_single_candidate_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-single")
    create_owned_conversation(client, conversation_id)
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
    conversation_id = uuid_for("decision-multiple")
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


def test_decisions_can_reference_same_owner_properties_from_other_conversations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_a = uuid_for("decision-isolation-a")
    conversation_b = uuid_for("decision-isolation-b")
    create_profile(conversation_a)
    create_profile(conversation_b)
    property_a = create_property(conversation_a, "A 房源")
    property_b = create_property(conversation_b, "B 房源")
    assert property_a.id is not None
    assert property_b.id is not None
    set_json_response(monkeypatch, ready_json(property_b.id))

    result_a = decision_service.generate(conversation_a)

    assert result_a.status == "ready"
    assert result_a.best_property_id == property_b.id

    set_json_response(monkeypatch, ready_json(property_a.id))
    result_b = decision_service.generate(conversation_b)

    assert result_b.status == "ready"
    assert result_b.best_property_id == property_a.id


def test_unknown_property_id_degrades_to_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-invalid-id")
    create_profile(conversation_id)
    create_property(conversation_id, "真实房源")
    set_json_response(monkeypatch, ready_json("unknown-property"))

    result = decision_service.generate(conversation_id)

    assert result.status == "waiting"
    assert result.best_property_id is None


def test_invalid_confidence_degrades_to_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-invalid-confidence")
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
    conversation_id = uuid_for("decision-invalid-json")
    create_profile(conversation_id)
    create_property(conversation_id, "JSON 测试")
    set_json_response(monkeypatch, "not JSON")

    result = decision_service.generate(conversation_id)

    assert result.status == "waiting"
    assert result.best_property_id is None


def test_ai_error_degrades_to_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("decision-ai-error")
    create_profile(conversation_id)
    create_property(conversation_id, "异常测试")

    def raise_ai_error(_prompt: str) -> str:
        raise RuntimeError("AI unavailable")

    set_json_response(monkeypatch, raise_ai_error)

    result = decision_service.generate(conversation_id)

    assert result.status == "waiting"
    assert result.best_property_id is None
