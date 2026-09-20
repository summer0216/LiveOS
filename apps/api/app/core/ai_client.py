import json
from collections.abc import Callable, Iterator
from time import perf_counter
from typing import Any, Literal, TypedDict

from openai import OpenAI, OpenAIError

from app.core.config import settings
from app.core.logger import logger

MessageRole = Literal["system", "user", "assistant"]


class AIMessage(TypedDict):
    role: MessageRole
    content: str


JSON_REQUEST_TIMEOUT_SECONDS = 90.0


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
        *,
        model: str | None = None,
        max_output_tokens: int | None = None,
    ) -> str:
        try:
            request_options = {}
            if max_output_tokens is not None:
                request_options["max_tokens"] = max_output_tokens

            response = self.client.with_options(
                timeout=JSON_REQUEST_TIMEOUT_SECONDS,
            ).chat.completions.create(
                model=model or settings.OPENAI_MODEL,
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
                **request_options,
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

    def generate_json_with_public_evidence_tool(
        self,
        prompt: str,
        *,
        tool: dict[str, Any],
        dispatch: Callable[[dict[str, Any]], str],
        model: str | None = None,
        max_output_tokens: int = 384,
    ) -> str:
        """Run one bounded model -> tool -> model turn for public evidence."""
        try:
            messages: list[Any] = [{"role": "user", "content": prompt}]
            first = self.client.with_options(
                timeout=JSON_REQUEST_TIMEOUT_SECONDS,
            ).chat.completions.create(
                model=model or settings.OPENAI_MODEL,
                messages=messages,
                tools=[tool],
                tool_choice="auto",
                temperature=0,
                max_tokens=192,
            )
            assistant_message = first.choices[0].message
            tool_calls = assistant_message.tool_calls or []
            if len(tool_calls) != 1:
                raise RuntimeError("LLM did not request exactly one public evidence tool call.")
            tool_call = tool_calls[0]
            if tool_call.function.name != "search_public_rental_evidence":
                raise RuntimeError("LLM requested an unsupported public evidence tool.")
            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError as error:
                raise RuntimeError("LLM returned invalid tool arguments.") from error
            if not isinstance(arguments, dict):
                raise TypeError("LLM returned invalid tool arguments.")

            messages.append(assistant_message)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": dispatch(arguments),
            })
            final = self.client.with_options(
                timeout=JSON_REQUEST_TIMEOUT_SECONDS,
            ).chat.completions.create(
                model=model or settings.OPENAI_MODEL,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=max_output_tokens,
            )
            content = final.choices[0].message.content
            if not content:
                raise RuntimeError("LLM returned an empty evidence interpretation.")
            return content
        except OpenAIError as error:
            raise RuntimeError(f"LLM public evidence request failed: {error}") from error


ai_client = AIClient()
