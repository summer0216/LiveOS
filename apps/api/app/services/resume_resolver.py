from dataclasses import dataclass

from pydantic import ValidationError

from app.models.profile import LivingProfile
from app.schemas.decision import DecisionResult
from app.schemas.decision_record import DecisionRecord
from app.stores.runtime import conversation_store, decision_record_store, profile_store


@dataclass(frozen=True)
class ResumableLivingState:
    conversation_id: str
    profile: LivingProfile | None
    decision: DecisionResult | None


class ResumeResolver:
    @staticmethod
    def _as_ready_decision(record: DecisionRecord) -> DecisionResult | None:
        try:
            return DecisionResult(
                status="ready",
                summary=record.summary,
                best_property_id=record.best_property_id,
                reasons=[item.model_copy(deep=True) for item in record.reasons],
                trade_offs=[
                    item.model_copy(deep=True) for item in record.trade_offs
                ],
                confidence=record.confidence,
            )
        except ValidationError:
            return None

    def _latest_ready_decision(
        self,
        conversation_id: str,
        records: list[DecisionRecord],
    ) -> DecisionResult | None:
        matching_records = sorted(
            (
                record
                for record in records
                if record.conversation_id == conversation_id
            ),
            key=lambda record: record.created_at,
            reverse=True,
        )
        for record in matching_records:
            decision = self._as_ready_decision(record)
            if decision is not None:
                return decision
        return None

    def resolve_for_owner(self, owner_id: str) -> ResumableLivingState | None:
        conversation_ids = conversation_store.list_ids_by_owner_activity(owner_id)
        if not conversation_ids:
            return None

        profile = profile_store.get_by_owner(owner_id)
        records = decision_record_store.list_by_owner(owner_id)
        for conversation_id in conversation_ids:
            decision = self._latest_ready_decision(conversation_id, records)
            if profile is not None or decision is not None:
                return ResumableLivingState(
                    conversation_id=conversation_id,
                    profile=profile,
                    decision=decision,
                )
        return None

    def resolve_conversation(
        self,
        owner_id: str,
        conversation_id: str,
    ) -> ResumableLivingState | None:
        if not conversation_store.belongs_to(conversation_id, owner_id):
            return None

        return ResumableLivingState(
            conversation_id=conversation_id,
            profile=profile_store.get_by_owner(owner_id),
            decision=self._latest_ready_decision(
                conversation_id,
                decision_record_store.list_by_owner(owner_id),
            ),
        )


resume_resolver = ResumeResolver()
