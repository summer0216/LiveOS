from fastapi import APIRouter, HTTPException, Request, Response

from app.api.ownership import anonymous_user_id, require_conversation_owner
from app.core.logger import logger
from app.models.decision_memory import DecisionMemory
from app.models.decision_memory_extraction import (
    DecisionMemoryExtractionStatus,
)
from app.schemas.decision_memory_api import (
    DecisionMemoryListResponse,
    DecisionMemoryRefreshResponse,
    DecisionMemoryResponse,
)
from app.services.decision_memory_extraction_service import (
    decision_memory_extraction_service,
)
from app.services.decision_memory_service import (
    DecisionMemoryValidationError,
    decision_memory_service,
)

router = APIRouter(
    prefix="/memories",
    tags=["memories"],
)


def require_conversation_id(conversation_id: str) -> str:
    normalized = conversation_id.strip()

    if not normalized:
        raise HTTPException(
            status_code=422,
            detail="Conversation ID must not be empty.",
        )

    return normalized


def to_memory_response(
    memory: DecisionMemory,
) -> DecisionMemoryResponse:
    return DecisionMemoryResponse(
        id=memory.id,
        conversation_id=memory.conversation_id,
        category=memory.category,
        content=memory.content,
        confidence=memory.confidence,
        evidence_record_ids=list(memory.evidence_record_ids),
        evidence_count=len(memory.evidence_record_ids),
        created_at=memory.created_at,
        updated_at=memory.updated_at,
    )


@router.get(
    "",
    response_model=DecisionMemoryListResponse,
)
def list_memories(
    conversation_id: str,
    request: Request,
    response: Response,
) -> DecisionMemoryListResponse:
    require_conversation_owner(conversation_id, anonymous_user_id(request, response))
    normalized_conversation_id = require_conversation_id(conversation_id)

    try:
        memories = decision_memory_service.list_memories(
            normalized_conversation_id,
        )
    except DecisionMemoryValidationError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.exception(
            "Failed to list Decision Memories for conversation %s.",
            normalized_conversation_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Decision memories could not be loaded.",
        ) from error

    return DecisionMemoryListResponse(
        conversation_id=normalized_conversation_id,
        memories=[to_memory_response(memory) for memory in memories],
    )


@router.post(
    "/refresh",
    response_model=DecisionMemoryRefreshResponse,
)
def refresh_memories(
    conversation_id: str,
    request: Request,
    response: Response,
) -> DecisionMemoryRefreshResponse:
    require_conversation_owner(conversation_id, anonymous_user_id(request, response))
    normalized_conversation_id = require_conversation_id(conversation_id)

    try:
        result = decision_memory_extraction_service.extract(
            normalized_conversation_id,
        )
    except Exception as error:
        logger.exception(
            "Unexpected Decision Memory refresh failure for conversation %s.",
            normalized_conversation_id,
        )
        raise HTTPException(
            status_code=502,
            detail="Memory extraction failed.",
        ) from error

    if result.status == DecisionMemoryExtractionStatus.FAILED:
        raise HTTPException(
            status_code=502,
            detail="Memory extraction failed.",
        )

    return DecisionMemoryRefreshResponse(
        conversation_id=result.conversation_id,
        status=result.status,
        history_record_count=result.history_record_count,
        candidate_count=result.candidate_count,
        saved_count=result.saved_count,
        rejected_count=result.rejected_count,
        memories=[to_memory_response(memory) for memory in result.memories],
    )
