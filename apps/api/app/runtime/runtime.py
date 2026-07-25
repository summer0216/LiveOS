from app.core.ai_client import ai_client


class AIRuntime:
    def chat(self, message: str) -> str:
        try:
            return ai_client.generate(message)

        except Exception:
            return "抱歉,AI 服务暂时不可用，请稍后重试。"


ai_runtime = AIRuntime()
