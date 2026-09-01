from datetime import UTC, datetime
from uuid import uuid4

from app.schemas.decision import DecisionResult
from app.schemas.decision_record import DecisionRecord
from app.services.conversation_manager import conversation_manager
from app.stores.runtime import decision_record_store


class DecisionRecordService:
    def save(
        self,
        conversation_id: str,
        decision: DecisionResult,
    ) -> DecisionRecord:
        if (
            decision.status != "ready"
            or decision.summary is None
            or decision.best_property_id is None
        ):
            raise ValueError("Only complete ready decisions can be recorded.")

        record = DecisionRecord(
            id=str(uuid4()),
            conversation_id=conversation_id,
            created_at=datetime.now(UTC),
            summary=decision.summary,
            best_property_id=decision.best_property_id,
            reasons=[reason.model_copy(deep=True) for reason in decision.reasons],
            trade_offs=[
                trade_off.model_copy(deep=True) for trade_off in decision.trade_offs
            ],
            confidence=decision.confidence,
            decision_gap=decision.decision_gap,
        )

        conversation_manager.get_or_create(conversation_id)
        return decision_record_store.save(record)

    def list_by_conversation(
        self,
        conversation_id: str,
    ) -> list[DecisionRecord]:
        return decision_record_store.list_by_conversation(conversation_id)

    def list(
        self,
        conversation_id: str,
    ) -> list[DecisionRecord]:
        return self.list_by_conversation(conversation_id)

    def get_by_id(
        self,
        conversation_id: str,
        record_id: str,
    ) -> DecisionRecord | None:
        return decision_record_store.get_by_id(conversation_id, record_id)

    def delete_conversation(
        self,
        conversation_id: str,
    ) -> None:
        decision_record_store.delete_conversation(conversation_id)


decision_record_service = DecisionRecordService()
