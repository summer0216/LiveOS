import re
from datetime import datetime, timezone
from threading import RLock
from uuid import UUID, uuid4

from app.models.decision_memory import (
    DecisionMemory,
    DecisionMemoryCandidate,
)
from app.stores.decision_memory_store import (
    DecisionMemoryStore,
    decision_memory_store,
)

MINIMUM_MEMORY_CONFIDENCE = 0.7
MINIMUM_MEMORY_CONTENT_LENGTH = 3
TRAILING_PUNCTUATION = "。.!！?？;；,，"


class DecisionMemoryValidationError(ValueError):
    pass


def normalize_memory_content(content: str) -> str:
    normalized = re.sub(r"\s+", " ", content.strip().lower())

    return normalized.rstrip(TRAILING_PUNCTUATION).rstrip()


def unique_evidence_ids(evidence_ids: list[UUID]) -> list[UUID]:
    return list(dict.fromkeys(evidence_ids))


class DecisionMemoryService:
    def __init__(
        self,
        store: DecisionMemoryStore,
    ) -> None:
        self._store = store
        self._lock = RLock()

    def save_candidate(
        self,
        conversation_id: str,
        candidate: DecisionMemoryCandidate,
    ) -> DecisionMemory:
        normalized_conversation_id = self._validate_conversation_id(
            conversation_id,
        )
        content = candidate.content.strip()

        if len(content) < MINIMUM_MEMORY_CONTENT_LENGTH:
            raise DecisionMemoryValidationError(
                "Memory content must contain at least 3 characters.",
            )

        if candidate.confidence < MINIMUM_MEMORY_CONFIDENCE:
            raise DecisionMemoryValidationError(
                "Memory confidence must be at least 0.7.",
            )

        evidence_record_ids = unique_evidence_ids(
            candidate.evidence_record_ids,
        )
        if len(evidence_record_ids) < 2:
            raise DecisionMemoryValidationError(
                "Memory requires at least 2 distinct evidence record IDs.",
            )

        normalized_content = normalize_memory_content(content)
        if len(normalized_content) < MINIMUM_MEMORY_CONTENT_LENGTH:
            raise DecisionMemoryValidationError(
                "Normalized memory content must contain at least 3 characters.",
            )

        with self._lock:
            existing = self._store.find_equivalent(
                conversation_id=normalized_conversation_id,
                category=candidate.category,
                normalized_content=normalized_content,
            )
            now = datetime.now(timezone.utc)

            if existing is None:
                memory = DecisionMemory(
                    id=uuid4(),
                    conversation_id=normalized_conversation_id,
                    category=candidate.category,
                    content=content,
                    normalized_content=normalized_content,
                    confidence=candidate.confidence,
                    evidence_record_ids=evidence_record_ids,
                    created_at=now,
                    updated_at=now,
                )
            else:
                memory = existing.model_copy(
                    update={
                        "confidence": max(
                            existing.confidence,
                            candidate.confidence,
                        ),
                        "evidence_record_ids": unique_evidence_ids(
                            [
                                *existing.evidence_record_ids,
                                *evidence_record_ids,
                            ],
                        ),
                        "updated_at": now,
                    },
                    deep=True,
                )

            return self._store.save(memory)

    def list_memories(
        self,
        conversation_id: str,
    ) -> list[DecisionMemory]:
        return self._store.list_by_conversation(
            self._validate_conversation_id(conversation_id),
        )

    def get_memory(
        self,
        conversation_id: str,
        memory_id: UUID,
    ) -> DecisionMemory | None:
        normalized_conversation_id = self._validate_conversation_id(
            conversation_id,
        )
        memory = self._store.get_by_id(memory_id)

        if (
            memory is None
            or memory.conversation_id != normalized_conversation_id
        ):
            return None

        return memory

    @staticmethod
    def _validate_conversation_id(conversation_id: str) -> str:
        normalized = conversation_id.strip()

        if not normalized:
            raise DecisionMemoryValidationError(
                "Conversation ID must not be empty.",
            )

        return normalized


decision_memory_service = DecisionMemoryService(decision_memory_store)
