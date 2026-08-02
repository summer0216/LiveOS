from typing import Any, Protocol
from uuid import UUID

from psycopg.types.json import Jsonb

from app.models.decision_memory import DecisionMemory, DecisionMemoryCategory
from app.stores.persistent import uuid_value
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
    @staticmethod
    def _from(row: dict[str, Any]) -> DecisionMemory:
        return DecisionMemory(
            id=row["id"],
            conversation_id=str(row["conversation_id"]),
            category=DecisionMemoryCategory(row["category"]),
            content=row["content"],
            normalized_content=row["normalized_content"],
            confidence=row["confidence"],
            evidence_record_ids=[
                UUID(value) for value in row["evidence_record_ids_json"]
            ],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def save(self, memory: DecisionMemory) -> DecisionMemory:
        with database.connect() as connection:
            connection.execute(
                """
                INSERT INTO decision_memories(
                    id, conversation_id, category, content, normalized_content,
                    confidence, evidence_record_ids_json, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    content = EXCLUDED.content,
                    normalized_content = EXCLUDED.normalized_content,
                    confidence = EXCLUDED.confidence,
                    evidence_record_ids_json = EXCLUDED.evidence_record_ids_json,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    memory.id,
                    uuid_value(memory.conversation_id),
                    memory.category.value,
                    memory.content,
                    memory.normalized_content,
                    memory.confidence,
                    Jsonb([str(value) for value in memory.evidence_record_ids]),
                    memory.created_at,
                    memory.updated_at,
                ),
            )
        return memory.model_copy(deep=True)

    def find_equivalent(
        self,
        conversation_id: str,
        category: DecisionMemoryCategory,
        normalized_content: str,
    ) -> DecisionMemory | None:
        with database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM decision_memories
                WHERE conversation_id = %s
                  AND category = %s
                  AND normalized_content = %s
                """,
                (uuid_value(conversation_id), category.value, normalized_content),
            ).fetchone()
        return self._from(row) if row else None

    def get_by_id(self, memory_id: UUID) -> DecisionMemory | None:
        with database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM decision_memories WHERE id = %s",
                (memory_id,),
            ).fetchone()
        return self._from(row) if row else None

    def list_by_conversation(self, conversation_id: str) -> list[DecisionMemory]:
        with database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM decision_memories
                WHERE conversation_id = %s
                ORDER BY updated_at DESC
                """,
                (uuid_value(conversation_id),),
            ).fetchall()
        return [self._from(row) for row in rows]

    def replace_conversation(
        self, conversation_id: str, memories: list[DecisionMemory]
    ) -> list[DecisionMemory]:
        conversation_uuid = uuid_value(conversation_id)
        with database.connect() as connection:
            connection.execute(
                "DELETE FROM decision_memories WHERE conversation_id = %s",
                (conversation_uuid,),
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO decision_memories(
                        id, conversation_id, category, content, normalized_content,
                        confidence, evidence_record_ids_json, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            memory.id,
                            conversation_uuid,
                            memory.category.value,
                            memory.content,
                            memory.normalized_content,
                            memory.confidence,
                            Jsonb([str(value) for value in memory.evidence_record_ids]),
                            memory.created_at,
                            memory.updated_at,
                        )
                        for memory in memories
                    ],
                )
        return [memory.model_copy(deep=True) for memory in memories]

    def clear(self) -> None:
        with database.connect() as connection:
            connection.execute("DELETE FROM decision_memories")


decision_memory_store = DecisionMemoryStore()
