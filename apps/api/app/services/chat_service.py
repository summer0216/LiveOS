import logging
from collections.abc import Iterator

from app.models.conversation import (
    Conversation,
    ConversationMessage,
)
from app.runtime.runtime import ai_runtime
from app.services.conversation_manager import conversation_manager
from app.services.profile_intelligence import profile_intelligence
from app.services.profile_manager import profile_manager

logger = logging.getLogger(__name__)


class ChatService:
    def _prepare_conversation(
        self,
        conversation_id: str,
        message: str,
    ) -> tuple[Conversation, list[ConversationMessage]]:
        conversation = conversation_manager.get_or_create(
            conversation_id,
        )

        conversation.add_user_message(message)

        history = conversation.get_messages()

        return conversation, history

    def _update_profile(
        self,
        conversation_id: str,
        history: list[ConversationMessage],
    ) -> None:
        """
        从当前会话历史中提取 Profile Analysis,
        并合并到对应的 Living Profile。

        Profile 更新失败时不阻断正常聊天。
        """

        try:
            analysis = profile_intelligence.extract(history)

            profile_manager.merge(
                conversation_id=conversation_id,
                patch=analysis.patch,
            )

        except Exception:
            logger.exception(
                "Failed to update living profile. " "conversation_id=%s",
                conversation_id,
            )

    def chat(
        self,
        conversation_id: str,
        message: str,
    ) -> str:
        conversation, history = self._prepare_conversation(
            conversation_id=conversation_id,
            message=message,
        )

        self._update_profile(
            conversation_id=conversation_id,
            history=history,
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

        self._update_profile(
            conversation_id=conversation_id,
            history=history,
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
