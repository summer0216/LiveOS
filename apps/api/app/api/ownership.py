from uuid import uuid4

from fastapi import HTTPException, Request, Response

from app.core.config import settings
from app.services.conversation_manager import conversation_manager
from app.stores.runtime import conversation_store

COOKIE_NAME = "liveos_anonymous_user"


def set_anonymous_cookie(response: Response, user_id: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        user_id,
        httponly=True,
        samesite="lax",
        path="/",
        secure=settings.cookie_secure,
    )


def anonymous_user_id(request: Request, response: Response) -> str:
    user_id = request.cookies.get(COOKIE_NAME)
    if user_id:
        conversation_store.ensure_user(user_id)
        return user_id
    user_id = str(uuid4())
    conversation_store.ensure_user(user_id)
    set_anonymous_cookie(response, user_id)
    return user_id


def require_conversation_owner(conversation_id: str, user_id: str) -> None:
    if not conversation_manager.belongs_to(conversation_id, user_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
