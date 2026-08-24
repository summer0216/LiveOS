import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from app.api.ownership import COOKIE_NAME, anonymous_user_id, set_anonymous_cookie
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_change import (
    decision_change_context,
    decision_change_payload,
)
from app.services.decision_feedback_context import decision_feedback_context

router = APIRouter(
    prefix="/chat",
    tags=["Chat"],
)
logger = logging.getLogger(__name__)
# Allow slow but valid model first-token/chunk delivery without removing the
# protection against a genuinely stalled stream.
STREAM_IDLE_TIMEOUT_SECONDS = 90.0
STREAM_ERROR_MESSAGE = "抱歉，LiveOS 暂时无法完成回复，请稍后重试。"


def _stream_events(
    chunks: Iterator[str],
    conversation_id: str | None = None,
) -> Iterator[str]:
    # Flush the response headers before the first model token is available.
    yield ": connected\n\n"

    executor = ThreadPoolExecutor(max_workers=1)
    iterator = iter(chunks)
    change_event_sent = False
    feedback_event_sent = False
    try:
        while True:
            future = executor.submit(next, iterator)
            try:
                chunk = future.result(timeout=STREAM_IDLE_TIMEOUT_SECONDS)
            except StopIteration:
                break
            except TimeoutError:
                logger.error(
                    "Streaming chat idle timeout after %.1f seconds",
                    STREAM_IDLE_TIMEOUT_SECONDS,
                )
                yield (
                    "event: error\n"
                    f"data: {json.dumps(STREAM_ERROR_MESSAGE, ensure_ascii=False)}\n\n"
                )
                break
            if not change_event_sent and conversation_id is not None:
                change_event_sent = True
                causes = decision_change_context.consume(conversation_id)
                if causes:
                    yield (
                        "event: decision-change\n"
                        f"data: {json.dumps(decision_change_payload(causes), ensure_ascii=False)}\n\n"
                    )
            if (
                not feedback_event_sent
                and conversation_id is not None
                and decision_feedback_context.is_relevant(conversation_id)
            ):
                feedback_event_sent = True
                yield "event: decision-feedback\ndata: true\n\n"
            yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
    except Exception:
        logger.exception("Streaming chat failed")
        yield (
            "event: error\n"
            f"data: {json.dumps(STREAM_ERROR_MESSAGE, ensure_ascii=False)}\n\n"
        )
    finally:
        if conversation_id is not None:
            decision_change_context.clear(conversation_id)
        executor.shutdown(wait=False, cancel_futures=True)


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest, raw_request: Request, response: Response
) -> ChatResponse:
    conversation_manager.get_or_create(
        request.conversation_id, anonymous_user_id(raw_request, response)
    )
    reply = chat_service.chat(
        conversation_id=request.conversation_id,
        message=request.message,
    )

    return ChatResponse(reply=reply)


@router.post("/stream")
async def chat_stream(request: ChatRequest, raw_request: Request, response: Response):
    user_id = anonymous_user_id(raw_request, response)
    conversation_manager.get_or_create(request.conversation_id, user_id)

    generator = chat_service.chat_stream(
        conversation_id=request.conversation_id,
        message=request.message,
    )

    stream_response = StreamingResponse(
        _stream_events(generator, request.conversation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    if raw_request.cookies.get(COOKIE_NAME) is None:
        set_anonymous_cookie(stream_response, user_id)
    return stream_response
