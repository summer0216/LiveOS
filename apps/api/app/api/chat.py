from fastapi import APIRouter

from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_service

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    reply = chat_service.chat(
        conversation_id=request.conversation_id,
        message=request.message,
    )

    return ChatResponse(reply=reply)
