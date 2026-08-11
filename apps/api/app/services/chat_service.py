import logging
from collections.abc import Iterator

from app.models.conversation import (
    Conversation,
    ConversationMessage,
)
from app.models.property import Property
from app.runtime.runtime import ai_runtime
from app.services.conversation_manager import conversation_manager
from app.services.profile_intelligence import profile_intelligence
from app.services.profile_manager import profile_manager
from app.services.property_intelligence import property_intelligence
from app.services.property_manager import property_manager

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

        conversation_manager.append_user_message(conversation_id, message)
        conversation = conversation_manager.get(conversation_id) or conversation
        history = conversation.get_messages()

        return conversation, history

    def _update_profile(
        self,
        conversation_id: str,
        history: list[ConversationMessage],
    ) -> None:
        """
        从当前会话历史中生成 Profile Analysis，
        并合并到对应的 Living Profile。

        Profile 更新失败时不阻断正常聊天。
        """

        try:
            analysis = profile_intelligence.analyze(history)

            profile_manager.merge(
                conversation_id=conversation_id,
                patch=analysis.patch,
                latest_insights=analysis.insights,
            )

            return analysis.insights

        except Exception:
            logger.exception(
                "Failed to update living profile. conversation_id=%s",
                conversation_id,
            )

            return []

    def chat(
        self,
        conversation_id: str,
        message: str,
    ) -> str:
        _conversation, history = self._prepare_conversation(
            conversation_id=conversation_id,
            message=message,
        )

        self._update_profile(
            conversation_id=conversation_id,
            history=history,
        )

        reply = ai_runtime.chat(history, profile_manager.get(conversation_id))

        if reply:
            conversation_manager.append_assistant_message(conversation_id, reply)

        return reply

    def chat_stream(
        self,
        conversation_id: str,
        message: str,
    ) -> Iterator[str]:
        _conversation, history = self._prepare_conversation(
            conversation_id=conversation_id,
            message=message,
        )

        self._update_profile(
            conversation_id=conversation_id,
            history=history,
        )

        assistant_reply_parts: list[str] = []

        for chunk in ai_runtime.chat_stream(
            history,
            profile_manager.get(conversation_id),
        ):
            if not chunk:
                continue

            assistant_reply_parts.append(chunk)
            yield chunk

        assistant_reply = "".join(assistant_reply_parts)

        if assistant_reply:
            conversation_manager.append_assistant_message(
                conversation_id,
                assistant_reply,
            )

    def update_property(
        self,
        conversation_id: str,
        description: str,
    ) -> Property:
        """
        理解房源描述，并更新当前会话的 Property State。
        """

        analysis = property_intelligence.analyze(
            description,
        )

        return property_manager.create(
            conversation_id=conversation_id,
            property_=analysis.property,
        )


chat_service = ChatService()
