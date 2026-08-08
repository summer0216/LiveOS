from typing import Any, Protocol
from uuid import UUID

from psycopg.types.json import Jsonb

from app.models.decision_memory import DecisionMemory, DecisionMemoryCategory
from app.stores.persistent import (
    optional_uuid,
    resolve_owner_id,
    uuid_value,
    validate_owner_source,
)
from app.stores.runtime import database


class DecisionMemoryStoreProtocol(Protocol):
    def save(self, memory: DecisionMemory) -> DecisionMemory: ...
    def find_equivalent(
        self,
        conversation_id: str,
        category: DecisionMemoryCategory,
        normalized_content: str,
    ) -> DecisionMemory | None: ...
    def find_equivalent_by_owner(
        self,
        owner_id: str | UUID,
        category: DecisionMemoryCategory,
        normalized_content: str,
    ) -> DecisionMemory | None: ...
    def get_by_id(self, memory_id: UUID) -> DecisionMemory | None: ...
    def get_by_id_for_conversation(
        self, conversation_id: str, memory_id: UUID
    ) -> DecisionMemory | None: ...
    def list_by_conversation(self, conversation_id: str) -> list[DecisionMemory]: ...
    def list_by_owner(self, owner_id: str | UUID) -> list[DecisionMemory]: ...
    def replace_conversation(
        self, conversation_id: str, memories: list[DecisionMemory]
    ) -> list[DecisionMemory]: ...
    def replace_for_owner(
        self,
        owner_id: str | UUID,
        memories: list[DecisionMemory],
        conversation_id: str | UUID | None = None,
    ) -> list[DecisionMemory]: ...


class DecisionMemoryStore:
    @staticmethod
    def _from(row: dict[str, Any]) -> DecisionMemory:
        return DecisionMemory(
            id=row["id"],
            conversation_id=(
                str(row["conversation_id"])
                if row["conversation_id"] is not None
                else str(row["owner_id"])
            ),
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
        owner_id = resolve_owner_id(database, memory.conversation_id)
        if owner_id is None:
            raise ValueError("Conversation owner could not be resolved.")
        return self.save_for_owner(owner_id, memory)

    def save_for_owner(
        self, owner_id: str | UUID, memory: DecisionMemory
    ) -> DecisionMemory:
        validate_owner_source(database, owner_id, memory.conversation_id)
        with database.connect() as connection:
            connection.execute(
                """
                INSERT INTO decision_memories(
                    id, owner_id, conversation_id, category, content, normalized_content,
                    confidence, evidence_record_ids_json, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    conversation_id = EXCLUDED.conversation_id,
                    content = EXCLUDED.content,
                    normalized_content = EXCLUDED.normalized_content,
                    confidence = EXCLUDED.confidence,
                    evidence_record_ids_json = EXCLUDED.evidence_record_ids_json,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    memory.id,
                    uuid_value(owner_id),
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
        owner_id = resolve_owner_id(database, conversation_id)
        if owner_id is None:
            return None
        return self.find_equivalent_by_owner(
            owner_id,
            category,
            normalized_content,
        )

    def find_equivalent_by_owner(
        self,
        owner_id: str | UUID,
        category: DecisionMemoryCategory,
        normalized_content: str,
    ) -> DecisionMemory | None:
        owner_uuid = optional_uuid(owner_id)
        if owner_uuid is None:
            return None
        with database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM decision_memories
                WHERE owner_id = %s
                  AND category = %s
                  AND normalized_content = %s
                """,
                (owner_uuid, category.value, normalized_content),
            ).fetchone()
        return self._from(row) if row else None

    def get_by_id(self, memory_id: UUID) -> DecisionMemory | None:
        with database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM decision_memories WHERE id = %s",
                (memory_id,),
            ).fetchone()
        return self._from(row) if row else None

    def get_by_id_for_conversation(
        self, conversation_id: str, memory_id: UUID
    ) -> DecisionMemory | None:
        with database.connect() as connection:
            row = connection.execute(
                """
                SELECT memory.* FROM decision_memories AS memory
                JOIN conversations AS conversation
                  ON conversation.anonymous_user_id = memory.owner_id
                WHERE conversation.id = %s AND memory.id = %s
                """,
                (uuid_value(conversation_id), memory_id),
            ).fetchone()
        return self._from(row) if row else None

    def list_by_conversation(self, conversation_id: str) -> list[DecisionMemory]:
        owner_id = resolve_owner_id(database, conversation_id)
        if owner_id is None:
            return []
        return self.list_by_owner(owner_id)

    def list_by_owner(self, owner_id: str | UUID) -> list[DecisionMemory]:
        owner_uuid = optional_uuid(owner_id)
        if owner_uuid is None:
            return []
        with database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM decision_memories
                WHERE owner_id = %s
                ORDER BY updated_at DESC
                """,
                (owner_uuid,),
            ).fetchall()
        return [self._from(row) for row in rows]

    def replace_conversation(
        self, conversation_id: str, memories: list[DecisionMemory]
    ) -> list[DecisionMemory]:
        conversation_uuid = uuid_value(conversation_id)
        owner_id = resolve_owner_id(database, conversation_uuid)
        if owner_id is None:
            raise ValueError("Conversation owner could not be resolved.")
        return self.replace_for_owner(owner_id, memories, conversation_uuid)

    def replace_for_owner(
        self,
        owner_id: str | UUID,
        memories: list[DecisionMemory],
        conversation_id: str | UUID | None = None,
    ) -> list[DecisionMemory]:
        owner_uuid = uuid_value(owner_id)
        for memory in memories:
            validate_owner_source(database, owner_uuid, memory.conversation_id)
        with database.connect() as connection:
            connection.execute(
                "DELETE FROM decision_memories WHERE owner_id = %s",
                (owner_uuid,),
            )
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO decision_memories(
                        id, owner_id, conversation_id, category, content,
                        normalized_content,
                        confidence, evidence_record_ids_json, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            memory.id,
                            owner_uuid,
                            (
                                optional_uuid(memory.conversation_id)
                                or optional_uuid(conversation_id)
                            ),
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
