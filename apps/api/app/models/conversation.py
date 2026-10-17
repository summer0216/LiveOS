from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

MessageRole = Literal["user", "assistant"]
MessageFeedback = Literal["POSITIVE", "NEGATIVE"]


@dataclass
class ConversationMessage:
    role: MessageRole
    content: str
    id: int | None = None
    created_at: datetime | None = None
    feedback: MessageFeedback | None = None


@dataclass
class Conversation:
    conversation_id: str
    messages: list[ConversationMessage] = field(default_factory=list)

    def add_user_message(self, content: str) -> None:
        self.messages.append(
            ConversationMessage(
                role="user",
                content=content,
            )
        )

    def add_assistant_message(self, content: str) -> None:
        self.messages.append(
            ConversationMessage(
                role="assistant",
                content=content,
            )
        )

    def get_messages(self) -> list[ConversationMessage]:
        return list(self.messages)
