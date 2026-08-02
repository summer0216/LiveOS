import json
from typing import Protocol
from uuid import UUID

from app.models.decision_memory import DecisionMemory, DecisionMemoryCategory
from app.stores.runtime import database


class DecisionMemoryStoreProtocol(Protocol):
    def save(self, memory: DecisionMemory) -> DecisionMemory: ...
    def find_equivalent(
        self,
        conversation_id: str,
        category: DecisionMemoryCategory,
        normalized_content: str,
    ) -> DecisionMemory | None: ...
    def get_by_id(self, memory_id: UUID) -> DecisionMemory | None: ...
    def list_by_conversation(self, conversation_id: str) -> list[DecisionMemory]: ...
    def replace_conversation(
        self, conversation_id: str, memories: list[DecisionMemory]
    ) -> list[DecisionMemory]: ...


class DecisionMemoryStore:
    def _from(self, row: object) -> DecisionMemory:
        from datetime import datetime

        return DecisionMemory(
            id=UUID(row["id"]),
            conversation_id=row["conversation_id"],
            category=DecisionMemoryCategory(row["category"]),
            content=row["content"],
            normalized_content=row["normalized_content"],
            confidence=row["confidence"],
            evidence_record_ids=[
                UUID(value) for value in json.loads(row["evidence_record_ids_json"])
            ],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def save(self, memory: DecisionMemory) -> DecisionMemory:
        with database.connect() as c:
            c.execute(
                "INSERT INTO decision_memories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET content=excluded.content,normalized_content=excluded.normalized_content,confidence=excluded.confidence,evidence_record_ids_json=excluded.evidence_record_ids_json,updated_at=excluded.updated_at",
                (
                    str(memory.id),
                    memory.conversation_id,
                    memory.category.value,
                    memory.content,
                    memory.normalized_content,
                    memory.confidence,
                    json.dumps([str(value) for value in memory.evidence_record_ids]),
                    memory.created_at.isoformat(),
                    memory.updated_at.isoformat(),
                ),
            )
        return memory.model_copy(deep=True)

    def find_equivalent(
        self,
        conversation_id: str,
        category: DecisionMemoryCategory,
        normalized_content: str,
    ) -> DecisionMemory | None:
        with database.connect() as c:
            row = c.execute(
                "SELECT * FROM decision_memories WHERE conversation_id=? AND category=? AND normalized_content=?",
                (conversation_id, category.value, normalized_content),
            ).fetchone()
        return self._from(row) if row else None

    def get_by_id(self, memory_id: UUID) -> DecisionMemory | None:
        with database.connect() as c:
            row = c.execute(
                "SELECT * FROM decision_memories WHERE id=?", (str(memory_id),)
            ).fetchone()
        return self._from(row) if row else None

    def list_by_conversation(self, conversation_id: str) -> list[DecisionMemory]:
        with database.connect() as c:
            rows = c.execute(
                "SELECT * FROM decision_memories WHERE conversation_id=? ORDER BY updated_at DESC",
                (conversation_id,),
            ).fetchall()
        return [self._from(row) for row in rows]

    def replace_conversation(
        self, conversation_id: str, memories: list[DecisionMemory]
    ) -> list[DecisionMemory]:
        with database.connect() as c:
            c.execute(
                "DELETE FROM decision_memories WHERE conversation_id=?",
                (conversation_id,),
            )
            c.executemany(
                "INSERT INTO decision_memories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        str(memory.id),
                        conversation_id,
                        memory.category.value,
                        memory.content,
                        memory.normalized_content,
                        memory.confidence,
                        json.dumps(
                            [str(value) for value in memory.evidence_record_ids]
                        ),
                        memory.created_at.isoformat(),
                        memory.updated_at.isoformat(),
                    )
                    for memory in memories
                ],
            )
        return [memory.model_copy(deep=True) for memory in memories]

    def clear(self) -> None:
        with database.connect() as c:
            c.execute("DELETE FROM decision_memories")


decision_memory_store = DecisionMemoryStore()
