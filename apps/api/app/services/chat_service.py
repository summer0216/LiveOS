from collections.abc import Iterator

from app.models.conversation import (
    Conversation,
    ConversationMessage,
)
from app.runtime.runtime import ai_runtime
from app.services.conversation_manager import conversation_manager


class ChatService:
    def _prepare_conversation(
        self,
        conversation_id: str,
        message: str,
    ) -> tuple[Conversation, list[ConversationMessage]]:
        """
        获取或创建 Conversation,
        保存当前用户消息，
        并返回本次请求所需的完整会话历史。
        """

        conversation = conversation_manager.get_or_create(
            conversation_id,
        )

        conversation.add_user_message(message)

        history = conversation.get_messages()

        return conversation, history

    def chat(
        self,
        conversation_id: str,
        message: str,
    ) -> str:
        conversation, history = self._prepare_conversation(
            conversation_id=conversation_id,
            message=message,
        )

        reply = ai_runtime.chat(history)

        if reply:
            conversation.add_assistant_message(reply)

        return reply

    def chat_stream(
        self,
        conversation_id: str,
        message: str,
    ) -> Iterator[str]:
        conversation, history = self._prepare_conversation(
            conversation_id=conversation_id,
            message=message,
        )

        assistant_reply_parts: list[str] = []

        for chunk in ai_runtime.chat_stream(history):
            if not chunk:
                continue

            assistant_reply_parts.append(chunk)
            yield chunk

        assistant_reply = "".join(assistant_reply_parts)

        if assistant_reply:
            conversation.add_assistant_message(
                assistant_reply,
            )


chat_service = ChatService()
