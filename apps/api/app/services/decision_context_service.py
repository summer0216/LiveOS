from app.core.logger import logger
from app.schemas.decision_context import DecisionContext
from app.services.decision_record_service import decision_record_service

RECENT_DECISION_LIMIT = 3


class DecisionContextService:
    def build_context(
        self,
        conversation_id: str,
    ) -> DecisionContext:
        try:
            records = decision_record_service.list_by_conversation(
                conversation_id,
            )
        except Exception:  # noqa: BLE001 - History failure must degrade Decision Context safely.
            logger.exception(
                "Failed to build Decision Context for conversation %s.",
                conversation_id,
            )
            records = []

        recent_decisions = sorted(
            records,
            key=lambda record: record.created_at,
            reverse=True,
        )[:RECENT_DECISION_LIMIT]

        return DecisionContext(
            conversation_id=conversation_id,
            recent_decisions=recent_decisions,
        )


decision_context_service = DecisionContextService()
