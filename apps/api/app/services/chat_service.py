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

    def chat_stream(
        self,
        conversation_id: str,
        message: str,
    ):
        return ai_runtime.chat_stream(
            conversation_id,
            message,
        )


chat_service = ChatService()
