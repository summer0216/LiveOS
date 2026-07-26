from typing import Literal

from pydantic import BaseModel


class ConversationMessageResponse(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[ConversationMessageResponse]
