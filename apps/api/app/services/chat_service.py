import logging
from collections.abc import Iterator
from time import perf_counter

from app.models.conversation import (
    Conversation,
    ConversationMessage,
)
from app.models.decision_change import (
    DecisionChangeCause,
    challenge_cause,
    feedback_cause,
    verification_outcome_cause,
)
from app.models.property import Property
from app.runtime.runtime import ai_runtime
from app.services.conversation_manager import conversation_manager
from app.services.decision_action_progress import decision_action_progress_service
from app.services.decision_challenge_context import decision_challenge_context
from app.services.decision_change import decision_change_context
from app.services.decision_feedback_context import decision_feedback_context
from app.services.decision_memory_service import decision_memory_service
from app.services.profile_intelligence import profile_intelligence
from app.services.profile_manager import profile_manager
from app.services.property_intelligence import property_intelligence
from app.services.property_manager import property_manager

logger = logging.getLogger(__name__)


class ChatService:
    def _prepare_conversation(
        self,
        conversation_id: str,
        message: str,
    ) -> tuple[Conversation, list[ConversationMessage]]:
        started_at = perf_counter()
        conversation = conversation_manager.get_or_create(
            conversation_id,
        )

        conversation_manager.append_user_message(conversation_id, message)
        conversation = conversation_manager.get(conversation_id) or conversation
        history = conversation.get_messages()
        logger.warning(
            "Conversation history load conversation_id=%s messages=%d elapsed_ms=%.1f",
            conversation_id,
            len(history),
            (perf_counter() - started_at) * 1000,
        )

        return conversation, history

    def _update_profile(
        self,
        conversation_id: str,
        history: list[ConversationMessage],
    ) -> tuple[DecisionChangeCause, ...]:
        """
        从当前会话历史中生成 Profile Analysis，
        并合并到对应的 Living Profile。

        Profile 更新失败时不阻断正常聊天。
        """

        started_at = perf_counter()
        logger.warning(
            "Profile intelligence start conversation_id=%s messages=%d",
            conversation_id,
            len(history),
        )
        try:
            analysis = profile_intelligence.analyze(history)
            logger.warning(
                "Profile intelligence complete conversation_id=%s elapsed_ms=%.1f",
                conversation_id,
                (perf_counter() - started_at) * 1000,
            )

            merge_started_at = perf_counter()
            merge_result = profile_manager.merge(
                conversation_id=conversation_id,
                patch=analysis.patch,
                latest_insights=analysis.insights,
            )
            decision_feedback_context.set(
                conversation_id,
                analysis.decision_feedback,
            )
            decision_challenge_context.set(
                conversation_id,
                analysis.decision_challenge,
            )
            if (
                analysis.action_progress_update.relevant
                or analysis.verification_outcome_update.relevant
            ):
                try:
                    decision_action_progress_service.apply_update(
                        conversation_id,
                        analysis.action_progress_update,
                        analysis.verification_outcome_update,
                    )
                    if analysis.verification_outcome_update.relevant:
                        action_state = decision_action_progress_service.current_state(
                            conversation_id,
                        )
                        if action_state is not None:
                            decision_memory_service.upsert_verification_learning(
                                action_state,
                            )
                except Exception:
                    logger.exception(
                        "Failed to persist Action Progress for conversation %s.",
                        conversation_id,
                    )
            logger.warning(
                "Profile merge complete conversation_id=%s changed=%s elapsed_ms=%.1f",
                conversation_id,
                merge_result.changed,
                (perf_counter() - merge_started_at) * 1000,
            )

            current_feedback_cause = feedback_cause(analysis.decision_feedback)
            current_challenge_cause = challenge_cause(analysis.decision_challenge)
            current_outcome_cause = verification_outcome_cause(
                analysis.verification_outcome_update,
            )
            return (
                *merge_result.causes,
                *((current_feedback_cause,) if current_feedback_cause else ()),
                *((current_challenge_cause,) if current_challenge_cause else ()),
                *((current_outcome_cause,) if current_outcome_cause else ()),
            )

        except Exception:
            decision_feedback_context.clear(conversation_id)
            decision_challenge_context.clear(conversation_id)
            logger.exception(
                "Failed to update living profile. conversation_id=%s elapsed_ms=%.1f",
                conversation_id,
                (perf_counter() - started_at) * 1000,
            )

            return ()

    def chat(
        self,
        conversation_id: str,
        message: str,
    ) -> str:
        _conversation, history = self._prepare_conversation(
            conversation_id=conversation_id,
            message=message,
        )

        self._update_profile(
            conversation_id=conversation_id,
            history=history,
        )

        reply = ai_runtime.chat(history, profile_manager.get(conversation_id))

        if reply:
            conversation_manager.append_assistant_message(conversation_id, reply)

        return reply

    def chat_stream(
        self,
        conversation_id: str,
        message: str,
    ) -> Iterator[str]:
        _conversation, history = self._prepare_conversation(
            conversation_id=conversation_id,
            message=message,
        )

        change_causes = self._update_profile(
            conversation_id=conversation_id,
            history=history,
        )
        decision_change_context.set(conversation_id, change_causes)

        return self._stream_assistant_reply(conversation_id, history)

    def _stream_assistant_reply(
        self,
        conversation_id: str,
        history: list[ConversationMessage],
    ) -> Iterator[str]:

        assistant_reply_parts: list[str] = []

        runtime_started_at = perf_counter()
        logger.warning("Runtime context build start conversation_id=%s", conversation_id)
        stream_started = False
        for chunk in ai_runtime.chat_stream(
            history,
            profile_manager.get(conversation_id),
        ):
            if not stream_started:
                stream_started = True
                logger.warning(
                    "LLM streaming first token conversation_id=%s context_elapsed_ms=%.1f",
                    conversation_id,
                    (perf_counter() - runtime_started_at) * 1000,
                )
            if not chunk:
                continue

            assistant_reply_parts.append(chunk)
            yield chunk

        if not stream_started:
            logger.warning(
                "LLM streaming completed without token conversation_id=%s context_elapsed_ms=%.1f",
                conversation_id,
                (perf_counter() - runtime_started_at) * 1000,
            )

        assistant_reply = "".join(assistant_reply_parts)

        if assistant_reply:
            conversation_manager.append_assistant_message(
                conversation_id,
                assistant_reply,
            )

    def update_property(
        self,
        conversation_id: str,
        description: str,
    ) -> Property:
        """
        理解房源描述，并更新当前会话的 Property State。
        """

        analysis = property_intelligence.analyze(
            description,
        )

        return property_manager.create(
            conversation_id=conversation_id,
            property_=analysis.property,
        )


chat_service = ChatService()
