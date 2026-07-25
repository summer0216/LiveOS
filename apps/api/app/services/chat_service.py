from app.runtime.runtime import ai_runtime


class ChatService:
    def chat(
        self,
        conversation_id: str,
        message: str,
    ) -> str:
        return ai_runtime.chat(
            conversation_id=conversation_id,
            message=message,
        )


chat_service = ChatService()
