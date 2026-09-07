from datetime import UTC, datetime
from uuid import uuid4

from app.models.decision_unknown import DecisionUnknown, DecisionUnknownStatus
from app.stores.runtime import decision_unknown_store


class DecisionUnknownService:
    def open_unknown(
        self,
        conversation_id: str,
        property_id: str,
        topic: str,
        meaning: str,
    ) -> DecisionUnknown:
        timestamp = datetime.now(UTC)
        return decision_unknown_store.upsert_open(
            DecisionUnknown(
                id=str(uuid4()),
                conversation_id=conversation_id,
                property_id=property_id,
                topic=topic,
                status=DecisionUnknownStatus.OPEN,
                meaning=meaning,
                created_at=timestamp,
                updated_at=timestamp,
            )
        )

    def list_open(
        self,
        conversation_id: str,
        property_id: str | None = None,
    ) -> list[DecisionUnknown]:
        return decision_unknown_store.list_open(conversation_id, property_id)

    def resolve_unknown(
        self,
        conversation_id: str,
        unknown_id: str,
    ) -> DecisionUnknown | None:
        return decision_unknown_store.update_status(
            conversation_id,
            unknown_id,
            DecisionUnknownStatus.RESOLVED,
        )


decision_unknown_service = DecisionUnknownService()
