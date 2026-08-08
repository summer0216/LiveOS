from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.models.decision_memory import (
    DecisionMemoryCandidate,
    DecisionMemoryCategory,
)
from app.services.conversation_manager import conversation_manager
from app.services.decision_memory_service import (
    DecisionMemoryValidationError,
    decision_memory_service,
)
from app.stores.decision_memory_store import decision_memory_store
from tests.ids import uuid_for

CONVERSATION_A = uuid_for("decision-memory-a")
CONVERSATION_B = uuid_for("decision-memory-b")


@pytest.fixture(autouse=True)
def clear_memory_store() -> Iterator[None]:
    decision_memory_store.clear()
    conversation_manager.get_or_create(CONVERSATION_A)
    conversation_manager.get_or_create(CONVERSATION_B)

    yield

    decision_memory_store.clear()


def candidate(
    *,
    category: DecisionMemoryCategory = DecisionMemoryCategory.PRIORITY,
    content: str = "用户优先考虑通勤。",
    confidence: float = 0.8,
    evidence_record_ids: list[UUID] | None = None,
) -> DecisionMemoryCandidate:
    return DecisionMemoryCandidate(
        category=category,
        content=content,
        confidence=confidence,
        evidence_record_ids=(
            evidence_record_ids
            if evidence_record_ids is not None
            else [uuid4(), uuid4()]
        ),
    )


def test_create_memory_adds_backend_metadata() -> None:
    memory = decision_memory_service.save_candidate(
        f" {CONVERSATION_A} ",
        candidate(),
    )

    assert isinstance(memory.id, UUID)
    assert memory.conversation_id == CONVERSATION_A
    assert memory.normalized_content == "用户优先考虑通勤"
    assert memory.created_at == memory.updated_at
    assert memory.created_at.tzinfo is not None
    assert len(decision_memory_service.list_memories(CONVERSATION_A)) == 1


def test_empty_content_is_rejected_without_saving() -> None:
    with pytest.raises(
        DecisionMemoryValidationError,
        match="at least 3 characters",
    ):
        decision_memory_service.save_candidate(
            CONVERSATION_A,
            candidate(content="   "),
        )

    assert decision_memory_service.list_memories(CONVERSATION_A) == []


def test_confidence_below_threshold_is_rejected() -> None:
    with pytest.raises(
        DecisionMemoryValidationError,
        match="at least 0.7",
    ):
        decision_memory_service.save_candidate(
            CONVERSATION_A,
            candidate(confidence=0.69),
        )


def test_confidence_boundary_is_allowed() -> None:
    memory = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(confidence=0.7),
    )

    assert memory.confidence == 0.7


def test_unknown_category_is_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        DecisionMemoryCandidate.model_validate(
            {
                "category": "unknown",
                "content": "用户优先考虑通勤。",
                "confidence": 0.8,
                "evidence_record_ids": [uuid4(), uuid4()],
            },
        )


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_confidence_outside_schema_range_is_rejected(
    confidence: float,
) -> None:
    with pytest.raises(ValidationError):
        candidate(confidence=confidence)


@pytest.mark.parametrize(
    "evidence_record_ids",
    [
        [],
        [uuid4()],
    ],
)
def test_insufficient_evidence_is_rejected(
    evidence_record_ids: list[UUID],
) -> None:
    with pytest.raises(
        DecisionMemoryValidationError,
        match="2 distinct",
    ):
        decision_memory_service.save_candidate(
            CONVERSATION_A,
            candidate(evidence_record_ids=evidence_record_ids),
        )


def test_duplicate_evidence_is_removed_in_input_order() -> None:
    evidence_a = uuid4()
    evidence_b = uuid4()

    memory = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(
            evidence_record_ids=[
                evidence_a,
                evidence_a,
                evidence_b,
            ],
        ),
    )

    assert memory.evidence_record_ids == [evidence_a, evidence_b]


def test_equivalent_memory_merges_metadata_and_evidence() -> None:
    evidence_a = uuid4()
    evidence_b = uuid4()
    evidence_c = uuid4()
    first = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(
            confidence=0.9,
            evidence_record_ids=[evidence_a, evidence_b],
        ),
    )
    second = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(
            content=" 用户优先考虑通勤 ",
            confidence=0.8,
            evidence_record_ids=[evidence_b, evidence_c],
        ),
    )

    assert second.id == first.id
    assert second.created_at == first.created_at
    assert second.updated_at > first.updated_at
    assert second.content == first.content
    assert second.normalized_content == first.normalized_content
    assert second.confidence == 0.9
    assert second.evidence_record_ids == [
        evidence_a,
        evidence_b,
        evidence_c,
    ]
    assert len(decision_memory_service.list_memories(CONVERSATION_A)) == 1


def test_trailing_punctuation_and_whitespace_normalize_for_merge() -> None:
    first = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(content="用户优先考虑通勤。"),
    )
    second = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(content="  用户优先考虑通勤  "),
    )

    assert second.id == first.id


def test_different_categories_do_not_merge() -> None:
    priority = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(category=DecisionMemoryCategory.PRIORITY),
    )
    preference = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(category=DecisionMemoryCategory.PREFERENCE),
    )

    assert priority.id != preference.id
    assert len(decision_memory_service.list_memories(CONVERSATION_A)) == 2


def test_same_owner_conversations_share_memories() -> None:
    memory_a = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(),
    )
    memory_b = decision_memory_service.save_candidate(
        CONVERSATION_B,
        candidate(),
    )

    assert memory_a.id == memory_b.id
    assert [
        memory.conversation_id
        for memory in decision_memory_service.list_memories(
            CONVERSATION_A,
        )
    ] == [CONVERSATION_A]
    assert [
        memory.conversation_id
        for memory in decision_memory_service.list_memories(
            CONVERSATION_B,
        )
    ] == [CONVERSATION_A]


def test_get_memory_accepts_another_conversation_for_same_owner() -> None:
    memory = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(),
    )

    assert decision_memory_service.get_memory(CONVERSATION_B, memory.id) == memory
    assert (
        decision_memory_service.get_memory(
            CONVERSATION_A,
            memory.id,
        )
        == memory
    )


def test_list_is_ordered_by_latest_update() -> None:
    first = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(content="用户优先考虑通勤。"),
    )
    second = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(content="用户重视居住空间。"),
    )
    updated_first = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(
            content="用户优先考虑通勤",
            confidence=0.9,
        ),
    )

    memories = decision_memory_service.list_memories(CONVERSATION_A)

    assert memories[0].id == updated_first.id
    assert memories[1].id == second.id
    assert first.id == updated_first.id


def test_store_returns_deep_copies() -> None:
    evidence_a = uuid4()
    evidence_b = uuid4()
    memory = decision_memory_service.save_candidate(
        CONVERSATION_A,
        candidate(evidence_record_ids=[evidence_a, evidence_b]),
    )

    memory.evidence_record_ids.append(uuid4())
    listed = decision_memory_service.list_memories(CONVERSATION_A)

    assert listed[0].evidence_record_ids == [evidence_a, evidence_b]


def test_empty_conversation_id_is_rejected() -> None:
    with pytest.raises(
        DecisionMemoryValidationError,
        match="must not be empty",
    ):
        decision_memory_service.save_candidate("   ", candidate())
