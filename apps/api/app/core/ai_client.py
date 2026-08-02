from collections.abc import Iterator
from typing import Literal, TypedDict

from openai import OpenAI, OpenAIError

from app.core.config import settings

MessageRole = Literal["system", "user", "assistant"]


class AIMessage(TypedDict):
    role: MessageRole
    content: str


class AIClient:
    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )

    def generate(
        self,
        messages: list[AIMessage],
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.7,
            )

            return response.choices[0].message.content or ""

        except OpenAIError as error:
            raise RuntimeError(
                f"LLM request failed: {error}",
            ) from error

    def generate_stream(
        self,
        messages: list[AIMessage],
    ) -> Iterator[str]:

        try:
            stream = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.7,
                stream=True,
            )

            for chunk in stream:
                if not chunk.choices:
                    continue

                content = chunk.choices[0].delta.content

                if content:
                    yield content

        except OpenAIError as error:
            raise RuntimeError(
                f"LLM streaming request failed: {error}",
            ) from error

    def generate_json(
        self,
        prompt: str,
    ) -> str:
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                response_format={
                    "type": "json_object",
                },
                temperature=0,
            )

            content = response.choices[0].message.content

            if not content:
                raise RuntimeError(
                    "LLM returned an empty JSON response.",
                )

            return content

        except OpenAIError as error:
            raise RuntimeError(
                f"LLM JSON request failed: {error}",
            ) from error


ai_client = AIClient()
