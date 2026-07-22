"""
LiveOS AI Runtime

Single Runtime
Multiple Logical Agents (Future)
"""


class AIRuntime:
    """
    LiveOS Single AI Runtime
    """

    def chat(self, message: str) -> str:
        """
        MVP Mock Runtime
        """

        return (
            "收到你的需求。\n\n"
            f"你说的是：{message}\n\n"
            "（Mock Reply，Sprint 3 后续将接入真正的 AI。）"
        )


ai_runtime = AIRuntime()
