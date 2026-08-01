from collections.abc import Iterator
from app.core.ai_client import AIMessage, ai_client
from app.models.conversation import ConversationMessage

SYSTEM_PROMPT = """
You are LiveOS, an AI Native Living Decision System.
Your role is to understand the user's living needs, constraints,
preferences and priorities through natural conversation.
Current MVP scenario: housing decision assistance.
Respond clearly and practically.
Do not invent property data.
Ask focused follow-up questions when important information is missing.
""".strip()


class AIRuntime:
    def build_context(
        self,
        history: list[ConversationMessage],
    ) -> list[AIMessage]:

        messages: list[AIMessage] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]
        messages.extend(
            {
                "role": message.role,
                "content": message.content,
            }
            for message in history
        )
        return messages

    def chat(
        self,
        history: list[ConversationMessage],
    ) -> str:
        context = self.build_context(history)
        return ai_client.generate(context)

    def chat_stream(
        self,
        history: list[ConversationMessage],
    ) -> Iterator[str]:

        context = self.build_context(history)
        yield from ai_client.generate_stream(context)


ai_runtime = AIRuntime()
