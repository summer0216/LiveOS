from app.runtime.runtime import ai_runtime


class ChatService:

    def chat(self, message: str) -> str:
        return ai_runtime.chat(message)


chat_service = ChatService()
