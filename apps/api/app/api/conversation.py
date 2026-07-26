from fastapi import APIRouter, HTTPException

from app.schemas.conversation import (
    ConversationHistoryResponse,
    ConversationMessageResponse,
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
) -> ConversationHistoryResponse:
    conversation = conversation_manager.get(conversation_id)

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found.",
        )

    messages = [
        ConversationMessageResponse(
            role=message.role,
            content=message.content,
        )
        for message in conversation.get_messages()
    ]

    return ConversationHistoryResponse(
        conversation_id=conversation.conversation_id,
        messages=messages,
    )
