from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.decision_memory import DecisionMemoryCategory
from app.runtime.memory_context import (
    DecisionMemoryContext,
    DecisionMemoryContextItem,
)
from app.schemas.decision import DecisionReason
from app.schemas.decision_context import DecisionContext
from app.schemas.decision_record import DecisionRecord
from app.services.decision_context_builder import (
    DecisionContextBuilder,
    decision_context_builder,
)
from app.services.decision_service import decision_service


class FakeHistoryBuilder:
    def __init__(
        self,
        records: list[DecisionRecord] | None = None,
    ) -> None:
        self.records = records or []
        self.calls: list[str] = []

    def build_context(
        self,
        conversation_id: str,
    ) -> DecisionContext:
        self.calls.append(conversation_id)

        return DecisionContext(
            conversation_id=conversation_id,
            recent_decisions=[
                record.model_copy(deep=True)
                for record in self.records
                if record.conversation_id == conversation_id
            ],
        )


class FakeMemoryBuilder:
    def __init__(
        self,
        memories: list[DecisionMemoryContextItem] | None = None,
        *,
        error: Exception | None = None,
    ) -> None:
        self.memories = memories or []
        self.error = error
        self.calls: list[str] = []

    def build(
        self,
        conversation_id: str,
    ) -> DecisionMemoryContext:
        self.calls.append(conversation_id)
        if self.error is not None:
            raise self.error

        return DecisionMemoryContext(
            conversation_id=conversation_id,
            memories=[memory.model_copy(deep=True) for memory in self.memories],
        )


def decision_record(
    conversation_id: str,
    index: int,
) -> DecisionRecord:
    return DecisionRecord(
        id=str(uuid4()),
        conversation_id=conversation_id,
        created_at=datetime.now(UTC),
        summary=f"Decision {index}",
        best_property_id=f"property-{index}",
        reasons=[
            DecisionReason(
                title="Context",
                description="History context record.",
            ),
        ],
        trade_offs=[],
        confidence=0.8,
    )


def memory_item(
    content: str,
) -> DecisionMemoryContextItem:
    return DecisionMemoryContextItem(
        category=DecisionMemoryCategory.PRIORITY,
        content=content,
        confidence=0.85,
        evidence_count=2,
        updated_at=datetime.now(UTC),
    )


def test_context_combines_history_and_memory() -> None:
    history = FakeHistoryBuilder(
        [decision_record("conversation-a", index) for index in range(3)],
    )
    memory = FakeMemoryBuilder(
        [memory_item("Memory A"), memory_item("Memory B")],
    )

    context = DecisionContextBuilder(history, memory).build(
        "conversation-a",
    )

    assert len(context.recent_decisions) == 3
    assert [item.content for item in context.memory_context.memories] == [
        "Memory A",
        "Memory B",
    ]


def test_empty_memory_preserves_history() -> None:
    history = FakeHistoryBuilder([decision_record("conversation-a", 1)])

    context = DecisionContextBuilder(
        history,
        FakeMemoryBuilder(),
    ).build("conversation-a")

    assert len(context.recent_decisions) == 1
    assert context.memory_context.memories == []


def test_empty_history_preserves_memory() -> None:
    context = DecisionContextBuilder(
        FakeHistoryBuilder(),
        FakeMemoryBuilder([memory_item("Memory A")]),
    ).build("conversation-a")

    assert context.recent_decisions == []
    assert len(context.memory_context.memories) == 1


def test_memory_failure_degrades_to_empty_memory_context() -> None:
    history = FakeHistoryBuilder([decision_record("conversation-a", 1)])
    memory = FakeMemoryBuilder(error=RuntimeError("Memory unavailable"))

    context = DecisionContextBuilder(history, memory).build(
        "conversation-a",
    )

    assert len(context.recent_decisions) == 1
    assert context.memory_context.conversation_id == "conversation-a"
    assert context.memory_context.memories == []


def test_history_failure_keeps_sprint14_empty_history_behavior() -> None:
    history = FakeHistoryBuilder()
    memory = FakeMemoryBuilder([memory_item("Memory A")])

    context = DecisionContextBuilder(history, memory).build(
        "conversation-a",
    )

    assert context.recent_decisions == []
    assert len(context.memory_context.memories) == 1


def test_conversation_isolation_is_forwarded_to_both_builders() -> None:
    history = FakeHistoryBuilder(
        [
            decision_record("conversation-a", 1),
            decision_record("conversation-b", 2),
        ],
    )
    memory = FakeMemoryBuilder([memory_item("Memory A")])

    context = DecisionContextBuilder(history, memory).build(
        " conversation-a ",
    )

    assert {record.conversation_id for record in context.recent_decisions} == {
        "conversation-a"
    }
    assert context.memory_context.conversation_id == "conversation-a"
    assert history.calls == ["conversation-a"]
    assert memory.calls == ["conversation-a"]


def test_each_build_reads_history_and_memory_without_cache() -> None:
    history = FakeHistoryBuilder([decision_record("conversation-a", 1)])
    memory = FakeMemoryBuilder([memory_item("Memory A")])
    builder = DecisionContextBuilder(history, memory)

    first = builder.build("conversation-a")
    history.records = [decision_record("conversation-a", 2)]
    memory.memories = [memory_item("Memory B")]
    second = builder.build("conversation-a")

    assert first.recent_decisions[0].summary == "Decision 1"
    assert first.memory_context.memories[0].content == "Memory A"
    assert second.recent_decisions[0].summary == "Decision 2"
    assert second.memory_context.memories[0].content == "Memory B"
    assert history.calls == ["conversation-a", "conversation-a"]
    assert memory.calls == ["conversation-a", "conversation-a"]


def test_builder_has_no_ai_prompt_runtime_or_store_dependency() -> None:
    history = FakeHistoryBuilder()
    memory = FakeMemoryBuilder()

    context = DecisionContextBuilder(history, memory).build(
        "conversation-a",
    )

    assert context.conversation_id == "conversation-a"
    assert history.calls == ["conversation-a"]
    assert memory.calls == ["conversation-a"]


def test_builder_does_not_mutate_history_or_memory() -> None:
    record = decision_record("conversation-a", 1)
    memory = memory_item("Memory A")
    record_snapshot = record.model_copy(deep=True)
    memory_snapshot = memory.model_copy(deep=True)
    history_builder = FakeHistoryBuilder([record])
    memory_builder = FakeMemoryBuilder([memory])

    DecisionContextBuilder(
        history_builder,
        memory_builder,
    ).build("conversation-a")

    assert record == record_snapshot
    assert memory == memory_snapshot
    assert history_builder.records == [record_snapshot]
    assert memory_builder.memories == [memory_snapshot]


def test_each_decision_invocation_uses_composed_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def build_context(conversation_id: str) -> DecisionContext:
        calls.append(conversation_id)
        return DecisionContext(
            conversation_id=conversation_id,
            memory_context=DecisionMemoryContext(
                conversation_id=conversation_id,
                memories=[],
            ),
        )

    monkeypatch.setattr(
        decision_context_builder,
        "build",
        build_context,
    )

    first = decision_service.generate("t16-context-invocation")
    second = decision_service.generate("t16-context-invocation")

    assert first.status == "waiting"
    assert second.status == "waiting"
    assert calls == [
        "t16-context-invocation",
        "t16-context-invocation",
    ]
