from typing import Protocol

from app.core.logger import logger
from app.runtime.memory_context import DecisionMemoryContext
from app.schemas.decision_context import DecisionContext
from app.services.decision_context_service import decision_context_service
from app.services.decision_feedback_context import decision_feedback_context
from app.services.decision_memory_context_builder import (
    decision_memory_context_builder,
)
from app.services.decision_memory_service import (
    DecisionMemoryValidationError,
)


class DecisionHistoryContextBuilder(Protocol):
    def build_context(
        self,
        conversation_id: str,
    ) -> DecisionContext: ...


class DecisionMemoryContextProvider(Protocol):
    def build(
        self,
        conversation_id: str,
    ) -> DecisionMemoryContext: ...


class DecisionContextBuilder:
    def __init__(
        self,
        history_builder: DecisionHistoryContextBuilder,
        memory_builder: DecisionMemoryContextProvider,
    ) -> None:
        self._history_builder = history_builder
        self._memory_builder = memory_builder

    def build(
        self,
        conversation_id: str,
    ) -> DecisionContext:
        normalized_conversation_id = conversation_id.strip()
        if not normalized_conversation_id:
            raise DecisionMemoryValidationError(
                "Conversation ID must not be empty.",
            )

        history_context = self._history_builder.build_context(
            normalized_conversation_id,
        )

        try:
            memory_context = self._memory_builder.build(
                normalized_conversation_id,
            )
        except Exception:  # noqa: BLE001 - Memory Context is optional runtime enhancement.
            logger.exception(
                (
                    "Failed to add Memory Context to Decision Context "
                    "for conversation %s."
                ),
                normalized_conversation_id,
            )
            memory_context = DecisionMemoryContext(
                conversation_id=normalized_conversation_id,
                memories=[],
            )

        context = DecisionContext(
            conversation_id=normalized_conversation_id,
            recent_decisions=history_context.recent_decisions,
            memory_context=memory_context,
            current_feedback=decision_feedback_context.consume(
                normalized_conversation_id,
            ),
        )

        logger.info(
            (
                "Built Decision Context for conversation %s: "
                "history_count=%d memory_count=%d."
            ),
            normalized_conversation_id,
            len(context.recent_decisions),
            len(context.memory_context.memories),
        )

        return context


decision_context_builder = DecisionContextBuilder(
    history_builder=decision_context_service,
    memory_builder=decision_memory_context_builder,
)
