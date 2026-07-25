from app.core.ai_client import ai_client


class AIRuntime:
    def chat(
        self,
        conversation_id: str,
        message: str,
    ) -> str:
        # Sprint 4 后续将使用 conversation_id
        # 加载会话历史和 Memory。
        _ = conversation_id

        return ai_client.generate(message)

    def chat_stream(
        self,
        conversation_id: str,
        message: str,
    ):

        yield from ai_client.generate_stream(message)


ai_runtime = AIRuntime()
