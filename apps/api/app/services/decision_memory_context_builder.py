from typing import Protocol

from pydantic import ValidationError

from app.core.logger import logger
from app.models.decision_memory import (
    DecisionMemory,
    DecisionMemoryCategory,
)
from app.runtime.memory_context import (
    DecisionMemoryContext,
    DecisionMemoryContextItem,
)
from app.services.decision_memory_service import (
    MINIMUM_MEMORY_CONFIDENCE,
    DecisionMemoryValidationError,
    decision_memory_service,
)

MEMORY_CONTEXT_LIMIT = 5


class DecisionMemoryReader(Protocol):
    def list_memories(
        self,
        conversation_id: str,
    ) -> list[DecisionMemory]: ...


class DecisionMemoryContextBuilder:
    def __init__(
        self,
        memory_service: DecisionMemoryReader,
    ) -> None:
        self._memory_service = memory_service

    def build(
        self,
        conversation_id: str,
    ) -> DecisionMemoryContext:
        normalized_conversation_id = conversation_id.strip()
        if not normalized_conversation_id:
            raise DecisionMemoryValidationError(
                "Conversation ID must not be empty.",
            )

        try:
            stored_memories = self._memory_service.list_memories(
                normalized_conversation_id,
            )
        except Exception:
            logger.exception(
                "Failed to build Memory Context for conversation %s.",
                normalized_conversation_id,
            )
            return DecisionMemoryContext(
                conversation_id=normalized_conversation_id,
                memories=[],
            )

        valid_memories = [
            memory
            for memory in stored_memories
            if self._is_runtime_safe(memory)
        ]
        selected_memories = sorted(
            valid_memories,
            key=lambda memory: (
                memory.confidence,
                memory.updated_at,
            ),
            reverse=True,
        )[:MEMORY_CONTEXT_LIMIT]
        context_items = [
            item
            for memory in selected_memories
            if (item := self._to_context_item(memory)) is not None
        ]

        logger.info(
            (
                "Built Memory Context for conversation %s: "
                "memory_count=%d selected_count=%d."
            ),
            normalized_conversation_id,
            len(stored_memories),
            len(context_items),
        )

        return DecisionMemoryContext(
            conversation_id=normalized_conversation_id,
            memories=context_items,
        )

    @staticmethod
    def _is_runtime_safe(memory: DecisionMemory) -> bool:
        return (
            isinstance(memory.category, DecisionMemoryCategory)
            and isinstance(memory.content, str)
            and bool(memory.content.strip())
            and not isinstance(memory.confidence, bool)
            and isinstance(memory.confidence, (int, float))
            and MINIMUM_MEMORY_CONFIDENCE <= memory.confidence <= 1.0
        )

    @staticmethod
    def _to_context_item(
        memory: DecisionMemory,
    ) -> DecisionMemoryContextItem | None:
        try:
            return DecisionMemoryContextItem(
                category=memory.category,
                content=memory.content.strip(),
                confidence=memory.confidence,
                evidence_count=len(memory.evidence_record_ids),
                updated_at=memory.updated_at,
            )
        except (TypeError, ValidationError):
            return None


decision_memory_context_builder = DecisionMemoryContextBuilder(
    decision_memory_service,
)
