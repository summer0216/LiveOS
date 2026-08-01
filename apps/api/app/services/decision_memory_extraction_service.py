from typing import Protocol
from uuid import UUID

from pydantic import ValidationError

from app.core.ai_client import ai_client
from app.core.logger import logger
from app.models.decision_memory import (
    DecisionMemory,
)
from app.models.profile import LivingProfile
from app.models.property import Property
from app.models.decision_memory_extraction import (
    DecisionMemoryExtractionOutput,
    DecisionMemoryExtractionResult,
    DecisionMemoryExtractionStatus,
)
from app.runtime.memory_evolution import (
    MemoryEvolutionCandidate,
    build_memory_evolution_prompt,
)
from app.schemas.decision_record import DecisionRecord
from app.services.decision_memory_service import (
    DecisionMemoryValidationError,
    MINIMUM_MEMORY_CONFIDENCE,
    decision_memory_service,
)
from app.services.decision_record_service import (
    decision_record_service,
)
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager

MINIMUM_HISTORY_RECORDS = 2
MAXIMUM_HISTORY_RECORDS = 10


class JSONGeneratingClient(Protocol):
    def generate_json(self, prompt: str) -> str:
        ...


class DecisionRecordSource(Protocol):
    def list_by_conversation(
        self,
        conversation_id: str,
    ) -> list[DecisionRecord]:
        ...


class MemoryCandidateService(Protocol):
    def list_memories(
        self,
        conversation_id: str,
    ) -> list[DecisionMemory]:
        ...

    def evolve_candidates(
        self,
        conversation_id: str,
        candidates: list[MemoryEvolutionCandidate],
    ) -> list[DecisionMemory]:
        ...


class ProfileSource(Protocol):
    def get(self, conversation_id: str) -> LivingProfile | None:
        ...


class PropertySource(Protocol):
    def list(self, conversation_id: str) -> list[Property]:
        ...


def validate_candidate_evidence(
    candidate: MemoryEvolutionCandidate,
    allowed_record_ids: set[UUID],
) -> list[UUID] | None:
    unique_ids = list(dict.fromkeys(candidate.evidence_record_ids))

    if len(unique_ids) < 2:
        return None

    if any(record_id not in allowed_record_ids for record_id in unique_ids):
        return None

    return unique_ids


class DecisionMemoryExtractionService:
    def __init__(
        self,
        decision_records: DecisionRecordSource,
        memory_service: MemoryCandidateService,
        json_client: JSONGeneratingClient,
        profile_source: ProfileSource | None = None,
        property_source: PropertySource | None = None,
    ) -> None:
        self._decision_records = decision_records
        self._memory_service = memory_service
        self._json_client = json_client
        self._profile_source = profile_source
        self._property_source = property_source

    def extract(
        self,
        conversation_id: str,
    ) -> DecisionMemoryExtractionResult:
        normalized_conversation_id = conversation_id.strip()
        if not normalized_conversation_id:
            return self._failed_result(conversation_id, 0)

        try:
            records_desc = self._decision_records.list_by_conversation(
                normalized_conversation_id,
            )
        except Exception:
            logger.exception(
                "Failed to read Decision History for Memory Extraction "
                "in conversation %s.",
                normalized_conversation_id,
            )
            return self._failed_result(normalized_conversation_id, 0)

        recent_records = records_desc[:MAXIMUM_HISTORY_RECORDS]
        history_record_count = len(recent_records)

        if history_record_count < MINIMUM_HISTORY_RECORDS:
            return DecisionMemoryExtractionResult(
                conversation_id=normalized_conversation_id,
                status=(
                    DecisionMemoryExtractionStatus.INSUFFICIENT_HISTORY
                ),
                history_record_count=history_record_count,
                candidate_count=0,
                saved_count=0,
                rejected_count=0,
                memories=[],
            )

        records_asc = list(reversed(recent_records))

        try:
            allowed_record_ids = {
                UUID(record.id)
                for record in records_asc
            }
            existing_memories = self._memory_service.list_memories(
                normalized_conversation_id,
            )
            profile = (
                self._profile_source.get(normalized_conversation_id)
                if self._profile_source is not None
                else None
            )
            properties = (
                self._property_source.list(normalized_conversation_id)
                if self._property_source is not None
                else []
            )
            prompt = build_memory_evolution_prompt(
                records_asc,
                existing_memories,
                profile,
                properties,
            )
            response = self._json_client.generate_json(prompt)
            output = DecisionMemoryExtractionOutput.model_validate_json(
                response,
            )
        except Exception:
            logger.exception(
                "Decision Memory Extraction failed for conversation %s.",
                normalized_conversation_id,
            )
            return self._failed_result(
                normalized_conversation_id,
                history_record_count,
            )

        rejected_count = 0
        validated_candidates: list[MemoryEvolutionCandidate] = []

        for raw_candidate in output.candidates:
            try:
                candidate = MemoryEvolutionCandidate.model_validate(
                    raw_candidate,
                )
                if candidate.confidence < MINIMUM_MEMORY_CONFIDENCE:
                    rejected_count += 1
                    continue
                evidence_ids = validate_candidate_evidence(
                    candidate,
                    allowed_record_ids,
                )
                if evidence_ids is None:
                    rejected_count += 1
                    continue

                validated_candidates.append(candidate.model_copy(
                    update={
                        "evidence_record_ids": evidence_ids,
                    },
                    deep=True,
                ))
            except (ValidationError, DecisionMemoryValidationError):
                rejected_count += 1
                continue

        try:
            evolved_memories = self._memory_service.evolve_candidates(
                normalized_conversation_id,
                validated_candidates,
            )
        except Exception:
            logger.exception(
                "Memory Evolution failed; existing Memory was retained.",
            )
            return self._failed_result(
                normalized_conversation_id,
                history_record_count,
            )

        return DecisionMemoryExtractionResult(
            conversation_id=normalized_conversation_id,
            status=DecisionMemoryExtractionStatus.COMPLETED,
            history_record_count=history_record_count,
            candidate_count=len(output.candidates),
            saved_count=len(validated_candidates),
            rejected_count=rejected_count,
            memories=evolved_memories,
        )

    @staticmethod
    def _failed_result(
        conversation_id: str,
        history_record_count: int,
    ) -> DecisionMemoryExtractionResult:
        return DecisionMemoryExtractionResult(
            conversation_id=conversation_id,
            status=DecisionMemoryExtractionStatus.FAILED,
            history_record_count=history_record_count,
            candidate_count=0,
            saved_count=0,
            rejected_count=0,
            memories=[],
        )


decision_memory_extraction_service = DecisionMemoryExtractionService(
    decision_records=decision_record_service,
    memory_service=decision_memory_service,
    json_client=ai_client,
    profile_source=profile_manager,
    property_source=property_manager,
)
