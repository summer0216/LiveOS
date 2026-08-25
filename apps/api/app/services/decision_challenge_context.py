from threading import RLock

from app.models.decision_challenge import DecisionChallenge


class DecisionChallengeContext:
    def __init__(self) -> None:
        self._challenge_by_conversation: dict[str, DecisionChallenge] = {}
        self._lock = RLock()

    def set(self, conversation_id: str, challenge: DecisionChallenge) -> None:
        with self._lock:
            if challenge.relevant:
                self._challenge_by_conversation[conversation_id] = challenge
            else:
                self._challenge_by_conversation.pop(conversation_id, None)

    def consume(self, conversation_id: str) -> DecisionChallenge | None:
        with self._lock:
            return self._challenge_by_conversation.pop(conversation_id, None)

    def clear(self, conversation_id: str) -> None:
        with self._lock:
            self._challenge_by_conversation.pop(conversation_id, None)


decision_challenge_context = DecisionChallengeContext()
