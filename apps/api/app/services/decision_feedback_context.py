from threading import RLock

from app.models.decision_feedback import DecisionRelevantFeedback


class DecisionFeedbackContext:
    def __init__(self) -> None:
        self._feedback_by_conversation: dict[str, DecisionRelevantFeedback] = {}
        self._lock = RLock()

    def set(
        self,
        conversation_id: str,
        feedback: DecisionRelevantFeedback,
    ) -> None:
        with self._lock:
            if feedback.relevant:
                self._feedback_by_conversation[conversation_id] = feedback
            else:
                self._feedback_by_conversation.pop(conversation_id, None)

    def is_relevant(self, conversation_id: str) -> bool:
        with self._lock:
            return conversation_id in self._feedback_by_conversation

    def consume(self, conversation_id: str) -> DecisionRelevantFeedback | None:
        with self._lock:
            return self._feedback_by_conversation.pop(conversation_id, None)

    def clear(self, conversation_id: str) -> None:
        with self._lock:
            self._feedback_by_conversation.pop(conversation_id, None)


decision_feedback_context = DecisionFeedbackContext()
