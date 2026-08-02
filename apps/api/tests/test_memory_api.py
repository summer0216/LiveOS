from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api import memories as memories_api
from app.main import app
from app.models.decision_memory import (
    DecisionMemory,
    DecisionMemoryCandidate,
    DecisionMemoryCategory,
)
from app.models.decision_memory_extraction import (
    DecisionMemoryExtractionResult,
    DecisionMemoryExtractionStatus,
)
from app.services.decision_memory_service import decision_memory_service
from app.stores.decision_memory_store import decision_memory_store
from tests.ownership import create_owned_conversation

client = TestClient(app)


class FakeExtractionService:
    def __init__(
        self,
        result: DecisionMemoryExtractionResult,
    ) -> None:
        self.result = result
        self.call_count = 0
        self.conversation_ids: list[str] = []

    def extract(
        self,
        conversation_id: str,
    ) -> DecisionMemoryExtractionResult:
        self.call_count += 1
        self.conversation_ids.append(conversation_id)

        return self.result


class SavingExtractionService:
    def __init__(self) -> None:
        self.call_count = 0

    def extract(
        self,
        conversation_id: str,
    ) -> DecisionMemoryExtractionResult:
        self.call_count += 1
        memory = decision_memory_service.save_candidate(
            conversation_id,
            memory_candidate(),
        )

        return extraction_result(
            conversation_id,
            status=DecisionMemoryExtractionStatus.COMPLETED,
            memories=[memory],
            candidate_count=1,
            saved_count=1,
        )


@pytest.fixture(autouse=True)
def clear_memory_api_data() -> Iterator[None]:
    decision_memory_store.clear()

    yield

    decision_memory_store.clear()


def memory_candidate(
    *,
    category: DecisionMemoryCategory = DecisionMemoryCategory.PRIORITY,
    content: str = "用户持续优先考虑通勤。",
    confidence: float = 0.84,
) -> DecisionMemoryCandidate:
    return DecisionMemoryCandidate(
        category=category,
        content=content,
        confidence=confidence,
        evidence_record_ids=[uuid4(), uuid4()],
    )


def extraction_result(
    conversation_id: str,
    *,
    status: DecisionMemoryExtractionStatus,
    memories: list[DecisionMemory] | None = None,
    history_record_count: int = 2,
    candidate_count: int = 0,
    saved_count: int = 0,
    rejected_count: int = 0,
) -> DecisionMemoryExtractionResult:
    return DecisionMemoryExtractionResult(
        conversation_id=conversation_id,
        status=status,
        history_record_count=history_record_count,
        candidate_count=candidate_count,
        saved_count=saved_count,
        rejected_count=rejected_count,
        memories=memories or [],
    )


def test_get_empty_memories_returns_200() -> None:
    create_owned_conversation(client, "memory-empty")
    response = client.get(
        "/api/memories",
        params={"conversation_id": "memory-empty"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "conversation_id": "memory-empty",
        "memories": [],
    }


def test_get_memories_maps_fields_and_updated_order() -> None:
    create_owned_conversation(client, "memory-list")
    first = decision_memory_service.save_candidate(
        "memory-list",
        memory_candidate(),
    )
    second = decision_memory_service.save_candidate(
        "memory-list",
        memory_candidate(
            category=DecisionMemoryCategory.PREFERENCE,
            content="用户持续偏好更大的空间。",
        ),
    )
    updated_first = decision_memory_service.save_candidate(
        "memory-list",
        memory_candidate(
            content="用户持续优先考虑通勤",
            confidence=0.9,
        ),
    )

    response = client.get(
        "/api/memories",
        params={"conversation_id": "memory-list"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert [item["id"] for item in payload["memories"]] == [
        str(updated_first.id),
        str(second.id),
    ]
    assert payload["memories"][0]["evidence_count"] == 4
    assert "normalized_content" not in payload["memories"][0]
    assert first.id == updated_first.id


def test_get_memories_is_isolated_by_conversation() -> None:
    create_owned_conversation(client, "memory-a")
    create_owned_conversation(client, "memory-b")
    memory_a = decision_memory_service.save_candidate(
        "memory-a",
        memory_candidate(),
    )
    decision_memory_service.save_candidate(
        "memory-b",
        memory_candidate(),
    )

    response = client.get(
        "/api/memories",
        params={"conversation_id": "memory-a"},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["memories"]] == [
        str(memory_a.id),
    ]


@pytest.mark.parametrize("conversation_id", ["", "   "])
def test_get_unowned_or_invalid_conversation_returns_404(
    conversation_id: str,
) -> None:
    response = client.get(
        "/api/memories",
        params={"conversation_id": conversation_id},
    )

    assert response.status_code == 404


def test_refresh_completed_maps_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_owned_conversation(client, "memory-refresh")
    memory = decision_memory_service.save_candidate(
        "memory-refresh",
        memory_candidate(),
    )
    fake = FakeExtractionService(
        extraction_result(
            "memory-refresh",
            status=DecisionMemoryExtractionStatus.COMPLETED,
            memories=[memory],
            candidate_count=1,
            saved_count=1,
        ),
    )
    monkeypatch.setattr(
        memories_api,
        "decision_memory_extraction_service",
        fake,
    )

    response = client.post(
        "/api/memories/refresh",
        params={"conversation_id": "memory-refresh"},
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "completed"
    assert payload["saved_count"] == 1
    assert payload["memories"][0]["evidence_count"] == 2
    assert "normalized_content" not in payload["memories"][0]
    assert fake.conversation_ids == ["memory-refresh"]


def test_refresh_completed_with_empty_candidates_returns_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_owned_conversation(client, "memory-refresh-empty")
    fake = FakeExtractionService(
        extraction_result(
            "memory-refresh-empty",
            status=DecisionMemoryExtractionStatus.COMPLETED,
        ),
    )
    monkeypatch.setattr(
        memories_api,
        "decision_memory_extraction_service",
        fake,
    )

    response = client.post(
        "/api/memories/refresh",
        params={"conversation_id": "memory-refresh-empty"},
    )

    assert response.status_code == 200
    assert response.json()["candidate_count"] == 0
    assert response.json()["memories"] == []


def test_refresh_insufficient_history_returns_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_owned_conversation(client, "memory-insufficient")
    fake = FakeExtractionService(
        extraction_result(
            "memory-insufficient",
            status=(DecisionMemoryExtractionStatus.INSUFFICIENT_HISTORY),
            history_record_count=1,
        ),
    )
    monkeypatch.setattr(
        memories_api,
        "decision_memory_extraction_service",
        fake,
    )

    response = client.post(
        "/api/memories/refresh",
        params={"conversation_id": "memory-insufficient"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "insufficient_history"


def test_refresh_failed_returns_safe_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_owned_conversation(client, "memory-failed")
    fake = FakeExtractionService(
        extraction_result(
            "memory-failed",
            status=DecisionMemoryExtractionStatus.FAILED,
        ),
    )
    monkeypatch.setattr(
        memories_api,
        "decision_memory_extraction_service",
        fake,
    )

    response = client.post(
        "/api/memories/refresh",
        params={"conversation_id": "memory-failed"},
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Memory extraction failed.",
    }


def test_refresh_unowned_or_invalid_conversation_does_not_call_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeExtractionService(
        extraction_result(
            "unused",
            status=DecisionMemoryExtractionStatus.COMPLETED,
        ),
    )
    monkeypatch.setattr(
        memories_api,
        "decision_memory_extraction_service",
        fake,
    )

    response = client.post(
        "/api/memories/refresh",
        params={"conversation_id": "   "},
    )

    assert response.status_code == 404
    assert fake.call_count == 0


def test_refresh_and_get_share_memory_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_owned_conversation(client, "memory-shared")
    fake = SavingExtractionService()
    monkeypatch.setattr(
        memories_api,
        "decision_memory_extraction_service",
        fake,
    )

    refresh_response = client.post(
        "/api/memories/refresh",
        params={"conversation_id": "memory-shared"},
    )
    get_response = client.get(
        "/api/memories",
        params={"conversation_id": "memory-shared"},
    )

    assert refresh_response.status_code == 200
    assert get_response.status_code == 200
    assert len(get_response.json()["memories"]) == 1
    assert fake.call_count == 1


def test_get_does_not_call_extraction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_owned_conversation(client, "memory-get-only")
    fake = FakeExtractionService(
        extraction_result(
            "unused",
            status=DecisionMemoryExtractionStatus.COMPLETED,
        ),
    )
    monkeypatch.setattr(
        memories_api,
        "decision_memory_extraction_service",
        fake,
    )

    response = client.get(
        "/api/memories",
        params={"conversation_id": "memory-get-only"},
    )

    assert response.status_code == 200
    assert fake.call_count == 0


def test_refresh_body_cannot_submit_candidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_owned_conversation(client, "memory-no-client-candidate")
    fake = FakeExtractionService(
        extraction_result(
            "memory-no-client-candidate",
            status=(DecisionMemoryExtractionStatus.INSUFFICIENT_HISTORY),
            history_record_count=0,
        ),
    )
    monkeypatch.setattr(
        memories_api,
        "decision_memory_extraction_service",
        fake,
    )

    response = client.post(
        "/api/memories/refresh",
        params={"conversation_id": "memory-no-client-candidate"},
        json={
            "candidate": {
                "content": "客户端伪造 Memory",
                "confidence": 1,
            },
        },
    )

    assert response.status_code == 200
    assert fake.call_count == 1
    assert (
        decision_memory_service.list_memories(
            "memory-no-client-candidate",
        )
        == []
    )
