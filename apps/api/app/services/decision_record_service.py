from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from app.schemas.decision import DecisionResult
from app.schemas.decision_record import DecisionRecord


class DecisionRecordService:
    def __init__(self) -> None:
        self._records: dict[str, list[DecisionRecord]] = {}
        self._lock = RLock()

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
            created_at=datetime.now(timezone.utc),
            summary=decision.summary,
            best_property_id=decision.best_property_id,
            reasons=[
                reason.model_copy(deep=True)
                for reason in decision.reasons
            ],
            trade_offs=[
                trade_off.model_copy(deep=True)
                for trade_off in decision.trade_offs
            ],
            confidence=decision.confidence,
        )

        with self._lock:
            self._records.setdefault(
                conversation_id,
                [],
            ).append(record)

        return record.model_copy(deep=True)

    def list_by_conversation(
        self,
        conversation_id: str,
    ) -> list[DecisionRecord]:
        with self._lock:
            return [
                record.model_copy(deep=True)
                for record in sorted(
                    self._records.get(conversation_id, []),
                    key=lambda record: record.created_at,
                    reverse=True,
                )
            ]

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
        with self._lock:
            for record in self._records.get(conversation_id, []):
                if record.id == record_id:
                    return record.model_copy(deep=True)

        return None

    def delete_conversation(
        self,
        conversation_id: str,
    ) -> None:
        with self._lock:
            self._records.pop(conversation_id, None)


decision_record_service = DecisionRecordService()
