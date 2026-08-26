import hashlib
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import RLock
from uuid import uuid4

from app.models.action_progress import (
    ActionProgressUpdate,
    CurrentActionProgress,
    DecisionActionState,
)
from app.schemas.decision_record import DecisionRecord
from app.stores.runtime import decision_action_state_store, decision_record_store

NEXT_DELIMITER = "下一步："


@dataclass(frozen=True)
class LogicalActionDescriptor:
    action_key: str
    next_text: str


def _normalized(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def _decision_signals(value: str) -> str:
    normalized_value = _normalized(value).replace("单人", "1人")
    numbers = re.findall(r"\d+(?:\.\d+)?", normalized_value)
    keywords = [
        keyword
        for keyword in (
            "不可行",
            "可行",
            "不建议",
            "建议",
            "不适合",
            "适合",
            "不接受",
            "接受",
            "不优先",
            "优先",
        )
        if keyword in normalized_value
    ]
    signals = "|".join([*numbers, *keywords])
    return signals or normalized_value


def _split_primary_next(summary: str) -> tuple[str, str] | None:
    index = summary.find(NEXT_DELIMITER)
    if index < 0:
        return None
    decision_text = summary[:index].strip()
    next_text = summary[index + len(NEXT_DELIMITER) :].strip()
    if not decision_text or not next_text:
        return None
    if re.search(r"\n|(?:^|\s)[1-9][.、)]|[•·]", next_text):
        return None
    return decision_text, next_text


def describe_logical_action(record: DecisionRecord) -> LogicalActionDescriptor | None:
    parts = _split_primary_next(record.summary)
    if parts is None:
        return None
    decision_text, next_text = parts
    payload = {
        "best_property_id": record.best_property_id,
        "decision_signals": _decision_signals(decision_text),
        "trade_offs": [
            {
                "title": _normalized(trade_off.title),
                "description": _normalized(trade_off.description),
            }
            for trade_off in record.trade_offs
        ],
        "next_text": _normalized(next_text),
    }
    action_key = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return LogicalActionDescriptor(action_key=action_key, next_text=next_text)


class DecisionActionProgressService:
    def __init__(self) -> None:
        self._lock = RLock()

    @staticmethod
    def _to_current(
        state: DecisionActionState | None,
        descriptor: LogicalActionDescriptor,
    ) -> CurrentActionProgress:
        return CurrentActionProgress(
            action_id=state.id if state is not None else None,
            next_text=descriptor.next_text,
            status=state.status if state is not None else None,
        )

    @staticmethod
    def _latest_record(conversation_id: str) -> DecisionRecord | None:
        records = [
            record
            for record in decision_record_store.list_by_conversation(conversation_id)
            if record.conversation_id == conversation_id
        ]
        return max(records, key=lambda record: record.created_at, default=None)

    def _reconcile(self, record: DecisionRecord) -> DecisionActionState | None:
        descriptor = describe_logical_action(record)
        if descriptor is None:
            decision_action_state_store.delete_conversation(record.conversation_id)
            return None

        existing = decision_action_state_store.get(record.conversation_id)
        timestamp = datetime.now(UTC)
        if existing is not None and existing.action_key == descriptor.action_key:
            state = existing.model_copy(
                update={
                    "decision_record_id": record.id,
                    "next_text": descriptor.next_text,
                    "updated_at": timestamp,
                }
            )
        else:
            state = DecisionActionState(
                id=str(uuid4()),
                conversation_id=record.conversation_id,
                decision_record_id=record.id,
                action_key=descriptor.action_key,
                next_text=descriptor.next_text,
                status=None,
                created_at=timestamp,
                updated_at=timestamp,
            )
        return decision_action_state_store.save(state)

    def reconcile_ready_record(
        self,
        record: DecisionRecord,
    ) -> CurrentActionProgress | None:
        with self._lock:
            state = self._reconcile(record)
            if state is None:
                return None
            descriptor = LogicalActionDescriptor(
                action_key=state.action_key,
                next_text=state.next_text,
            )
            return self._to_current(state, descriptor)

    def apply_update(
        self,
        conversation_id: str,
        update: ActionProgressUpdate,
    ) -> CurrentActionProgress | None:
        if not update.relevant or update.status is None:
            return self.resolve_current(conversation_id)

        with self._lock:
            record = self._latest_record(conversation_id)
            if record is None:
                return None
            state = self._reconcile(record)
            if state is None:
                return None
            state = decision_action_state_store.save(
                state.model_copy(
                    update={
                        "status": update.status,
                        "updated_at": datetime.now(UTC),
                    }
                )
            )
            return CurrentActionProgress(
                action_id=state.id,
                next_text=state.next_text,
                status=state.status,
            )

    def resolve_for_record(
        self,
        record: DecisionRecord,
    ) -> CurrentActionProgress | None:
        descriptor = describe_logical_action(record)
        if descriptor is None:
            return None
        state = decision_action_state_store.get(record.conversation_id)
        if state is None or state.action_key != descriptor.action_key:
            return self._to_current(None, descriptor)
        return self._to_current(state, descriptor)

    def resolve_current(self, conversation_id: str) -> CurrentActionProgress | None:
        record = self._latest_record(conversation_id)
        return self.resolve_for_record(record) if record is not None else None

    def delete_conversation(self, conversation_id: str) -> None:
        decision_action_state_store.delete_conversation(conversation_id)


decision_action_progress_service = DecisionActionProgressService()
