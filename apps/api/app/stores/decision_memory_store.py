from threading import RLock
from uuid import UUID

from app.models.decision_memory import (
    DecisionMemory,
    DecisionMemoryCategory,
)


class DecisionMemoryStore:
    def __init__(self) -> None:
        self._memories: dict[UUID, DecisionMemory] = {}
        self._lock = RLock()

    def save(
        self,
        memory: DecisionMemory,
    ) -> DecisionMemory:
        stored_memory = memory.model_copy(deep=True)

        with self._lock:
            self._memories[stored_memory.id] = stored_memory

        return stored_memory.model_copy(deep=True)

    def find_equivalent(
        self,
        conversation_id: str,
        category: DecisionMemoryCategory,
        normalized_content: str,
    ) -> DecisionMemory | None:
        with self._lock:
            for memory in self._memories.values():
                if (
                    memory.conversation_id == conversation_id
                    and memory.category == category
                    and memory.normalized_content == normalized_content
                ):
                    return memory.model_copy(deep=True)

        return None

    def get_by_id(
        self,
        memory_id: UUID,
    ) -> DecisionMemory | None:
        with self._lock:
            memory = self._memories.get(memory_id)

            return (
                memory.model_copy(deep=True)
                if memory is not None
                else None
            )

    def list_by_conversation(
        self,
        conversation_id: str,
    ) -> list[DecisionMemory]:
        with self._lock:
            return [
                memory.model_copy(deep=True)
                for memory in sorted(
                    (
                        memory
                        for memory in self._memories.values()
                        if memory.conversation_id == conversation_id
                    ),
                    key=lambda memory: memory.updated_at,
                    reverse=True,
                )
            ]

    def clear(self) -> None:
        with self._lock:
            self._memories.clear()


decision_memory_store = DecisionMemoryStore()
