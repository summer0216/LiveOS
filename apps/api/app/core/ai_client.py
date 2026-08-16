from collections.abc import Iterator
from time import perf_counter
from typing import Literal, TypedDict

from openai import OpenAI, OpenAIError

from app.core.config import settings
from app.core.logger import logger

MessageRole = Literal["system", "user", "assistant"]


class AIMessage(TypedDict):
    role: MessageRole
    content: str


class AIClient:
    def __init__(self) -> None:
        self.client = OpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            timeout=30.0,
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

        started_at = perf_counter()
        try:
            stream = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.7,
                stream=True,
            )
            logger.warning(
                "LLM streaming response opened elapsed_ms=%.1f",
                (perf_counter() - started_at) * 1000,
            )

            first_token_logged = False
            for chunk in stream:
                if not chunk.choices:
                    continue

                content = chunk.choices[0].delta.content

                if content:
                    if not first_token_logged:
                        logger.warning(
                            "LLM streaming first token elapsed_ms=%.1f",
                            (perf_counter() - started_at) * 1000,
                        )
                        first_token_logged = True
                    yield content

        except OpenAIError as error:
            logger.exception(
                "LLM streaming request failed elapsed_ms=%.1f",
                (perf_counter() - started_at) * 1000,
            )
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
