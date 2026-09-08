import logging
from collections.abc import Iterator
from time import perf_counter

from app.core.config import settings
from app.models.action_progress import VerificationOutcomeStatus
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
from app.models.property import GeographicStatus, Property
from app.runtime.runtime import ai_runtime
from app.services.conversation_manager import conversation_manager
from app.services.decision_action_progress import decision_action_progress_service
from app.services.decision_challenge_context import decision_challenge_context
from app.services.decision_change import decision_change_context
from app.services.decision_feedback_context import decision_feedback_context
from app.services.decision_memory_service import decision_memory_service
from app.services.decision_record_service import decision_record_service
from app.services.decision_unknown_service import decision_unknown_service
from app.services.profile_intelligence import profile_intelligence
from app.services.profile_manager import profile_manager
from app.services.property_intelligence import property_intelligence
from app.services.property_manager import property_manager
from app.services.transit_duration import transit_duration_service

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
            properties = property_manager.list(conversation_id)
            if properties:
                analysis = profile_intelligence.analyze(history, properties)
            else:
                analysis = profile_intelligence.analyze(history)
            materialized_choices = property_manager.materialize_choices(
                conversation_id,
                analysis.choices,
            )
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
            merged_profile = getattr(merge_result, "profile", None)
            if (
                merged_profile is not None
                and merged_profile.work_location
                and merged_profile.geographic_status == GeographicStatus.UNRESOLVED
            ):
                profile_manager.resolve_work_geographic_grounding(
                    conversation_id,
                    context_location=merged_profile.preferred_city or "深圳市",
                    api_key=settings.AMAP_WEB_SERVICE_KEY,
                )
            geographic_context = (
                merged_profile.preferred_city
                if merged_profile is not None
                else None
            ) or analysis.patch.preferred_city or "深圳市"
            for property_ in materialized_choices:
                if property_.geographic_status == GeographicStatus.UNRESOLVED:
                    property_manager.resolve_geographic_grounding(
                        property_.id or "",
                        conversation_id,
                        context_location=geographic_context,
                        api_key=settings.AMAP_WEB_SERVICE_KEY,
                    )
            if analysis.geographic_clarification.relevant:
                clarification = analysis.geographic_clarification
                property_manager.update_geographic_grounding(
                    clarification.target_property_id,
                    conversation_id,
                    geographic_identity=clarification.geographic_identity,
                    geographic_precision=clarification.geographic_precision,
                    geographic_status=GeographicStatus.GROUNDED,
                    lng=clarification.lng,
                    lat=clarification.lat,
                )
            grounded_profile = profile_manager.get(conversation_id)
            if (
                grounded_profile is not None
                and grounded_profile.geographic_status == GeographicStatus.GROUNDED
                and grounded_profile.lng is not None
                and grounded_profile.lat is not None
            ):
                for property_ in materialized_choices:
                    current_property = property_manager.get_scoped(
                        property_.id or "",
                        conversation_id,
                    )
                    if (
                        current_property is None
                        or current_property.geographic_status != GeographicStatus.GROUNDED
                        or current_property.lng is None
                        or current_property.lat is None
                    ):
                        continue
                    commute_minutes = transit_duration_service.calculate_minutes(
                        origin_lng=grounded_profile.lng,
                        origin_lat=grounded_profile.lat,
                        destination_lng=current_property.lng,
                        destination_lat=current_property.lat,
                        api_key=settings.AMAP_WEB_SERVICE_KEY,
                    )
                    property_manager.update_commute_minutes(
                        current_property.id or "",
                        conversation_id,
                        commute_minutes,
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
                        verified_action = (
                            decision_action_progress_service.latest_verified_state(
                                conversation_id,
                            )
                        )
                        if verified_action is not None:
                            if verified_action.outcome_status in {
                                VerificationOutcomeStatus.DISCONFIRMED,
                                VerificationOutcomeStatus.INCONCLUSIVE,
                            }:
                                decision_record_service.invalidate_recommendation(
                                    conversation_id,
                                    verified_action.decision_record_id,
                                )
                            if verified_action.unknown_id is not None:
                                decision_unknown_service.resolve_unknown(
                                    conversation_id,
                                    verified_action.unknown_id,
                                )
                            decision_memory_service.upsert_verification_learning(
                                verified_action,
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
        logger.warning(
            "Runtime context build start conversation_id=%s", conversation_id
        )
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
