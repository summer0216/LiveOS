from app.core.ai_client import ai_client


class AIRuntime:
    def chat(self, message: str) -> str:
        return ai_client.generate(message)


ai_runtime = AIRuntime()