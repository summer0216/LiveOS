from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.conversation import MessageFeedback
from app.models.environment_eligibility import EnvironmentEligibilityResult


class MessageFeedbackRequest(BaseModel):
    feedback: MessageFeedback | None


class MessageFeedbackResponse(MessageFeedbackRequest):
    message_id: str


class ConversationMessageResponse(BaseModel):
    id: str
    created_at: datetime
    role: Literal["user", "assistant"]
    content: str
    feedback: MessageFeedback | None = None


class ConversationHistoryResponse(BaseModel):
    conversation_id: str
    messages: list[ConversationMessageResponse]
    environment_eligibility: EnvironmentEligibilityResult | None = None
