"""
LiveOS AI Runtime

Single Runtime
Multiple Logical Agents (Future)
"""

import app.core.ai_client as ai_client

class AIRuntime:
    """
    LiveOS Single AI Runtime
    """

    def chat(self, message: str) -> str:
        """
        MVP Mock Runtime
        """
        reply = ai_client.generate(message)
        return reply


ai_runtime = AIRuntime()
