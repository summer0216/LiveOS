from fastapi import APIRouter

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
)

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)


@router.post(
    "",
    response_model=ChatResponse,
)
async def chat(
    request: ChatRequest,
):
    """
    MVP Mock Chat API
    """

    return ChatResponse(
        reply=f"收到：{request.message}"
    )