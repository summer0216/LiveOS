import re
from collections.abc import Iterable
from datetime import UTC, datetime
from threading import RLock
from uuid import UUID, uuid4

from app.models.action_progress import DecisionActionState, VerificationOutcomeStatus
from app.models.decision_memory import (
    DecisionMemory,
    DecisionMemoryCandidate,
    DecisionMemoryCategory,
)
from app.runtime.memory_evolution import MemoryEvolutionCandidate
from app.services.conversation_manager import conversation_manager
from app.stores.decision_memory_store import (
    DecisionMemoryStoreProtocol,
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
        store: DecisionMemoryStoreProtocol,
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
        conversation_manager.get_or_create(normalized_conversation_id)
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
            now = datetime.now(UTC)

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

    def upsert_verification_learning(
        self,
        state: DecisionActionState,
    ) -> DecisionMemory | None:
        if state.outcome_status is None or not state.verification_evidence:
            return None

        normalized_conversation_id = self._validate_conversation_id(
            state.conversation_id,
        )
        source_action_id = UUID(state.id)
        source_record_id = UUID(state.decision_record_id)
        content = self._verification_learning_content(state.outcome_status)
        now = datetime.now(UTC)

        with self._lock:
            existing = self._store.find_by_source_action_id(
                normalized_conversation_id,
                source_action_id,
            )
            memory = DecisionMemory(
                id=existing.id if existing is not None else uuid4(),
                conversation_id=normalized_conversation_id,
                category=DecisionMemoryCategory.EVIDENCE_RELIABILITY,
                content=content,
                normalized_content=normalize_memory_content(content),
                confidence=0.8,
                evidence_record_ids=[source_record_id],
                source_action_id=source_action_id,
                source_action_key=state.action_key,
                source_outcome_status=state.outcome_status,
                source_decision_record_id=source_record_id,
                created_at=existing.created_at if existing is not None else now,
                updated_at=now,
            )
            return self._store.save(memory)

    def evolve_candidates(
        self,
        conversation_id: str,
        candidates: list[MemoryEvolutionCandidate],
    ) -> list[DecisionMemory]:
        normalized_conversation_id = self._validate_conversation_id(
            conversation_id,
        )
        conversation_manager.get_or_create(normalized_conversation_id)

        with self._lock:
            existing_memories = self._store.list_by_conversation(
                normalized_conversation_id,
            )
            memories_by_id = {memory.id: memory for memory in existing_memories}
            evolved_by_id = memories_by_id.copy()
            now = datetime.now(UTC)
            touched_ids: list[UUID] = []

            for candidate in candidates:
                content, normalized_content, evidence_ids = self._validate_candidate(
                    candidate
                )
                existing = (
                    evolved_by_id.get(candidate.memory_id)
                    if candidate.memory_id is not None
                    else self._find_equivalent(
                        evolved_by_id.values(),
                        candidate,
                        normalized_content,
                    )
                )

                if candidate.memory_id is not None and existing is None:
                    raise DecisionMemoryValidationError(
                        "Evolution target must be an existing Memory.",
                    )
                if existing is not None and existing.category != candidate.category:
                    raise DecisionMemoryValidationError(
                        "Memory category cannot change during evolution.",
                    )

                if existing is None:
                    memory = DecisionMemory(
                        id=uuid4(),
                        conversation_id=normalized_conversation_id,
                        category=candidate.category,
                        content=content,
                        normalized_content=normalized_content,
                        confidence=candidate.confidence,
                        evidence_record_ids=evidence_ids,
                        created_at=now,
                        updated_at=now,
                    )
                else:
                    is_reinforcement = existing.normalized_content == normalized_content
                    memory = existing.model_copy(
                        update={
                            "content": content,
                            "normalized_content": normalized_content,
                            "confidence": (
                                max(
                                    existing.confidence,
                                    candidate.confidence,
                                )
                                if is_reinforcement
                                else candidate.confidence
                            ),
                            "evidence_record_ids": unique_evidence_ids(
                                [
                                    *existing.evidence_record_ids,
                                    *evidence_ids,
                                ],
                            ),
                            "updated_at": now,
                        },
                        deep=True,
                    )

                evolved_by_id[memory.id] = memory
                if memory.id not in touched_ids:
                    touched_ids.append(memory.id)

            self._store.replace_conversation(
                normalized_conversation_id,
                list(evolved_by_id.values()),
            )

            return [
                evolved_by_id[memory_id].model_copy(deep=True)
                for memory_id in touched_ids
            ]

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
        return self._store.get_by_id_for_conversation(
            normalized_conversation_id,
            memory_id,
        )

    @staticmethod
    def _verification_learning_content(
        outcome_status: VerificationOutcomeStatus,
    ) -> str:
        if outcome_status == VerificationOutcomeStatus.CONFIRMED:
            return "关键事实已确认，可据此评估对应约束。"
        if outcome_status == VerificationOutcomeStatus.DISCONFIRMED:
            return "关键事实被证伪时，不应高置信度判断其满足对应约束。"
        return "关键事实未能确认时，不应高置信度判断其满足对应约束。"

    @staticmethod
    def _find_equivalent(
        memories: Iterable[DecisionMemory],
        candidate: DecisionMemoryCandidate,
        normalized_content: str,
    ) -> DecisionMemory | None:
        for memory in memories:
            if (
                memory.category == candidate.category
                and memory.normalized_content == normalized_content
            ):
                return memory

        return None

    @staticmethod
    def _validate_candidate(
        candidate: DecisionMemoryCandidate,
    ) -> tuple[str, str, list[UUID]]:
        content = candidate.content.strip()
        if len(content) < MINIMUM_MEMORY_CONTENT_LENGTH:
            raise DecisionMemoryValidationError(
                "Memory content must contain at least 3 characters.",
            )
        if candidate.confidence < MINIMUM_MEMORY_CONFIDENCE:
            raise DecisionMemoryValidationError(
                "Memory confidence must be at least 0.7.",
            )
        evidence_ids = unique_evidence_ids(candidate.evidence_record_ids)
        if len(evidence_ids) < 2:
            raise DecisionMemoryValidationError(
                "Memory requires at least 2 distinct evidence record IDs.",
            )
        normalized_content = normalize_memory_content(content)
        if len(normalized_content) < MINIMUM_MEMORY_CONTENT_LENGTH:
            raise DecisionMemoryValidationError(
                "Normalized memory content must contain at least 3 characters.",
            )
        return content, normalized_content, evidence_ids

    @staticmethod
    def _validate_conversation_id(conversation_id: str) -> str:
        normalized = conversation_id.strip()

        if not normalized:
            raise DecisionMemoryValidationError(
                "Conversation ID must not be empty.",
            )

        return normalized


decision_memory_service = DecisionMemoryService(decision_memory_store)
