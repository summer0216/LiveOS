from fastapi import APIRouter, HTTPException, Request, Response

from app.api.ownership import anonymous_user_id, require_conversation_owner
from app.schemas.conversation import (
    ConversationHistoryResponse,
    ConversationMessageResponse,
    MessageFeedbackRequest,
    MessageFeedbackResponse,
)
from app.services.conversation_manager import conversation_manager

router = APIRouter(
    prefix="/conversations",
    tags=["Conversations"],
)


@router.get(
    "/{conversation_id}",
    response_model=ConversationHistoryResponse,
)
async def get_conversation_history(
    conversation_id: str,
    request: Request,
    response: Response,
) -> ConversationHistoryResponse:
    require_conversation_owner(conversation_id, anonymous_user_id(request, response))
    conversation = conversation_manager.get(conversation_id)

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    messages = [
        ConversationMessageResponse(
            id=str(message.id),
            created_at=message.created_at,
            role=message.role,
            content=message.content,
            feedback=message.feedback,
        )
        for message in conversation.get_messages()
    ]

    return ConversationHistoryResponse(
        conversation_id=conversation.conversation_id,
        messages=messages,
    )


@router.put("/{conversation_id}/messages/{message_id}/feedback", response_model=MessageFeedbackResponse)
async def set_message_feedback(
    conversation_id: str, message_id: int, payload: MessageFeedbackRequest,
    request: Request, response: Response,
) -> MessageFeedbackResponse:
    user_id = anonymous_user_id(request, response)
    require_conversation_owner(conversation_id, user_id)
    try:
        conversation_manager.set_message_feedback(conversation_id, message_id, user_id, payload.feedback)
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return MessageFeedbackResponse(message_id=str(message_id), feedback=payload.feedback)
