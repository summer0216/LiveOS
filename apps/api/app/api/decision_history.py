from fastapi import APIRouter, HTTPException, Request, Response

from app.api.ownership import anonymous_user_id, require_conversation_owner
from app.core.logger import logger
from app.schemas.decision_record import (
    DecisionHistoryResponse,
    DecisionRecord,
)
from app.services.conversation_manager import conversation_manager
from app.services.decision_record_service import decision_record_service

router = APIRouter(
    prefix="/conversations/{conversation_id}/decisions/history",
    tags=["Decision History"],
)


def ensure_conversation_exists(conversation_id: str) -> None:
    if conversation_manager.get(conversation_id) is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )


@router.get(
    "",
    response_model=DecisionHistoryResponse,
)
def list_decision_history(
    conversation_id: str,
    request: Request,
    response: Response,
) -> DecisionHistoryResponse:
    require_conversation_owner(conversation_id, anonymous_user_id(request, response))
    ensure_conversation_exists(conversation_id)

    try:
        records = decision_record_service.list_by_conversation(
            conversation_id,
        )
    except Exception as error:
        logger.exception(
            "Failed to read Decision History for conversation %s.",
            conversation_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Decision history could not be loaded.",
        ) from error

    return DecisionHistoryResponse(
        conversation_id=conversation_id,
        items=records,
        total=len(records),
    )


@router.get(
    "/{record_id}",
    response_model=DecisionRecord,
)
def get_decision_record(
    conversation_id: str,
    record_id: str,
    request: Request,
    response: Response,
) -> DecisionRecord:
    require_conversation_owner(conversation_id, anonymous_user_id(request, response))
    ensure_conversation_exists(conversation_id)

    try:
        record = decision_record_service.get_by_id(
            conversation_id=conversation_id,
            record_id=record_id,
        )
    except Exception as error:
        logger.exception(
            "Failed to read Decision Record %s for conversation %s.",
            record_id,
            conversation_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Decision history could not be loaded.",
        ) from error

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="Decision record not found.",
        )

    return record
