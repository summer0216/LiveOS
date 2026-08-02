from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.decision_memory import (
    DecisionMemory,
    DecisionMemoryCategory,
)
from app.services.decision_memory_context_builder import (
    MEMORY_CONTEXT_LIMIT,
    DecisionMemoryContextBuilder,
)
from app.services.decision_memory_service import (
    DecisionMemoryValidationError,
)


class FakeMemoryService:
    def __init__(
        self,
        memories: list[DecisionMemory] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.memories = memories or []
        self.error = error
        self.calls: list[str] = []

    def list_memories(
        self,
        conversation_id: str,
    ) -> list[DecisionMemory]:
        self.calls.append(conversation_id)
        if self.error is not None:
            raise self.error

        return [
            memory.model_copy(deep=True)
            for memory in self.memories
            if memory.conversation_id == conversation_id
        ]


def stored_memory(
    *,
    conversation_id: str = "conversation-a",
    category: DecisionMemoryCategory = DecisionMemoryCategory.PRIORITY,
    content: str = "用户优先考虑通勤。",
    confidence: float = 0.8,
    updated_at: datetime | None = None,
    evidence_count: int = 2,
) -> DecisionMemory:
    timestamp = updated_at or datetime.now(UTC)

    return DecisionMemory(
        id=uuid4(),
        conversation_id=conversation_id,
        category=category,
        content=content,
        normalized_content=content.strip(),
        confidence=confidence,
        evidence_record_ids=[uuid4() for _ in range(evidence_count)],
        created_at=timestamp,
        updated_at=timestamp,
    )


def builder_for(
    service: FakeMemoryService,
) -> DecisionMemoryContextBuilder:
    return DecisionMemoryContextBuilder(service)


def test_empty_memory_returns_empty_context() -> None:
    service = FakeMemoryService()

    context = builder_for(service).build(" conversation-a ")

    assert context.conversation_id == "conversation-a"
    assert context.memories == []
    assert service.calls == ["conversation-a"]


def test_single_memory_maps_runtime_safe_fields_only() -> None:
    memory = stored_memory()

    context = builder_for(FakeMemoryService([memory])).build(
        "conversation-a",
    )

    assert len(context.memories) == 1
    assert context.memories[0].model_dump() == {
        "category": DecisionMemoryCategory.PRIORITY,
        "content": "用户优先考虑通勤。",
        "confidence": 0.8,
        "evidence_count": 2,
        "updated_at": memory.updated_at,
    }
    context_fields = type(context.memories[0]).model_fields
    assert "id" not in context_fields
    assert "normalized_content" not in context_fields
    assert "evidence_record_ids" not in context_fields


def test_six_memories_returns_top_five() -> None:
    memories = [
        stored_memory(
            content=f"Memory {index}",
            confidence=0.7 + index * 0.01,
        )
        for index in range(6)
    ]

    context = builder_for(FakeMemoryService(memories)).build(
        "conversation-a",
    )

    assert len(context.memories) == MEMORY_CONTEXT_LIMIT
    assert [item.content for item in context.memories] == [
        "Memory 5",
        "Memory 4",
        "Memory 3",
        "Memory 2",
        "Memory 1",
    ]


def test_memories_are_sorted_by_confidence_descending() -> None:
    memories = [
        stored_memory(content="0.90", confidence=0.90),
        stored_memory(content="0.85", confidence=0.85),
        stored_memory(content="0.95", confidence=0.95),
    ]

    context = builder_for(FakeMemoryService(memories)).build(
        "conversation-a",
    )

    assert [item.confidence for item in context.memories] == [
        0.95,
        0.90,
        0.85,
    ]


def test_equal_confidence_is_sorted_by_updated_at_descending() -> None:
    now = datetime.now(UTC)
    memories = [
        stored_memory(content="old", updated_at=now),
        stored_memory(
            content="new",
            updated_at=now + timedelta(minutes=1),
        ),
    ]

    context = builder_for(FakeMemoryService(memories)).build(
        "conversation-a",
    )

    assert [item.content for item in context.memories] == ["new", "old"]


def test_conversations_are_isolated() -> None:
    service = FakeMemoryService(
        [
            stored_memory(
                conversation_id="conversation-a",
                content="Memory A",
            ),
            stored_memory(
                conversation_id="conversation-b",
                content="Memory B",
            ),
        ],
    )

    context = builder_for(service).build("conversation-a")

    assert [item.content for item in context.memories] == ["Memory A"]
    assert service.calls == ["conversation-a"]


@pytest.mark.parametrize(
    "confidence",
    [0.69, -1.0, 1.01, True],
)
def test_invalid_confidence_is_skipped(
    confidence: float,
) -> None:
    invalid = stored_memory().model_copy(
        update={"confidence": confidence},
    )

    context = builder_for(FakeMemoryService([invalid])).build(
        "conversation-a",
    )

    assert context.memories == []


def test_empty_content_is_skipped() -> None:
    invalid = stored_memory().model_copy(update={"content": "   "})

    context = builder_for(FakeMemoryService([invalid])).build(
        "conversation-a",
    )

    assert context.memories == []


def test_invalid_category_is_skipped() -> None:
    invalid = stored_memory().model_copy(
        update={"category": "unknown"},
    )

    context = builder_for(FakeMemoryService([invalid])).build(
        "conversation-a",
    )

    assert context.memories == []


def test_service_failure_degrades_to_empty_context() -> None:
    service = FakeMemoryService(error=RuntimeError("Memory unavailable"))

    context = builder_for(service).build("conversation-a")

    assert context.conversation_id == "conversation-a"
    assert context.memories == []


def test_empty_conversation_id_is_rejected_before_service_call() -> None:
    service = FakeMemoryService()

    with pytest.raises(
        DecisionMemoryValidationError,
        match="must not be empty",
    ):
        builder_for(service).build("   ")

    assert service.calls == []


def test_builder_has_no_ai_or_history_dependency() -> None:
    service = FakeMemoryService([stored_memory()])

    context = builder_for(service).build("conversation-a")

    assert len(context.memories) == 1
    assert service.calls == ["conversation-a"]


def test_builder_does_not_mutate_stored_memory() -> None:
    memory = stored_memory(content="  用户优先考虑通勤。  ")
    snapshot = memory.model_copy(deep=True)
    service = FakeMemoryService([memory])

    builder_for(service).build("conversation-a")

    assert memory == snapshot
    assert service.memories == [snapshot]


def test_evidence_count_is_derived_from_evidence_ids() -> None:
    memory = stored_memory(evidence_count=4)

    context = builder_for(FakeMemoryService([memory])).build(
        "conversation-a",
    )

    assert context.memories[0].evidence_count == 4


def test_each_build_reads_memory_service_without_cache() -> None:
    service = FakeMemoryService([stored_memory(content="first")])
    builder = builder_for(service)

    first = builder.build("conversation-a")
    service.memories = [stored_memory(content="second")]
    second = builder.build("conversation-a")

    assert first.memories[0].content == "first"
    assert second.memories[0].content == "second"
    assert service.calls == ["conversation-a", "conversation-a"]
