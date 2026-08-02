from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from app.api.ownership import COOKIE_NAME, anonymous_user_id, set_anonymous_cookie
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest, raw_request: Request, response: Response
) -> ChatResponse:
    conversation_manager.get_or_create(
        request.conversation_id, anonymous_user_id(raw_request, response)
    )
    reply = chat_service.chat(
        conversation_id=request.conversation_id,
        message=request.message,
    )

    return ChatResponse(reply=reply)


@router.post("/stream")
async def chat_stream(request: ChatRequest, raw_request: Request, response: Response):
    user_id = anonymous_user_id(raw_request, response)
    conversation_manager.get_or_create(request.conversation_id, user_id)

    generator = chat_service.chat_stream(
        conversation_id=request.conversation_id,
        message=request.message,
    )

    stream_response = StreamingResponse(
        generator,
        media_type="text/plain",
    )
    if raw_request.cookies.get(COOKIE_NAME) is None:
        set_anonymous_cookie(stream_response, user_id)
    return stream_response
