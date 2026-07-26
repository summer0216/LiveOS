from email import message

from app.runtime.runtime import ai_runtime
from app.services.conversation_manager import conversation_manager


class ChatService:
    def chat(
        self,
        conversation_id: str,
        message: str,
    ) -> str:
        conversation = conversation_manager.get_or_create(conversation_id)
        conversation.add_user_message(message)
        reply = ai_runtime.chat(
            conversation_id,
            message,
        )
        conversation.add_ai_message(reply)
        return reply

    def chat_stream(
        self,
        conversation_id: str,
        message: str,
    ):
        conversation = conversation_manager.get_or_create(
            conversation_id,
        )

        # 保存用户消息
        conversation.add_user_message(message)

        # 用于最后保存完整回复
        assistant_reply = ""

        for chunk in ai_runtime.chat_stream(
            conversation_id,
            message,
        ):
            assistant_reply += chunk

            # 立即返回给前端
            yield chunk

        # Streaming 完成以后
        conversation.add_assistant_message(
            assistant_reply,
        )


chat_service = ChatService()
