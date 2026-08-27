from dataclasses import asdict
from threading import RLock
from typing import Any

from app.models.decision_change import (
    ChallengeCause,
    DecisionChangeCause,
    FeedbackCause,
    ProfileMutationCause,
    VerificationOutcomeCause,
)

PROFILE_LABELS = {
    "work_location": "工作地点",
    "budget": "预算",
    "commute_minutes": "通勤要求",
    "preferred_city": "意向城市",
    "family_size": "居住人数",
    "has_pet": "宠物情况",
}


def _format_value(cause: ProfileMutationCause, value: object) -> str:
    if cause.field == "budget" and isinstance(value, int):
        return f"¥{value:,}"
    if cause.field == "commute_minutes" and isinstance(value, int):
        return f"{value} 分钟"
    if cause.field == "family_size" and isinstance(value, int):
        return f"{value} 人"
    if cause.field == "has_pet" and isinstance(value, bool):
        return "有宠物" if value else "无宠物"
    return str(value)


def _format_profile_cause(cause: ProfileMutationCause) -> str:
    label = PROFILE_LABELS[cause.field]
    if cause.operation == "CLEAR":
        return f"原{label}条件已撤销。"
    current = _format_value(cause, cause.after)
    if cause.before is None:
        return f"{label}已设为{current}。"
    previous = _format_value(cause, cause.before)
    return f"{label}从{previous}调整为{current}。"


def _format_feedback_cause(cause: FeedbackCause) -> str:
    if cause.observed_commute_minutes is not None:
        minutes = cause.observed_commute_minutes
        if cause.judgment == "unacceptable":
            return f"你实际体验了约 {minutes} 分钟通勤，并确认这个时间无法接受。"
        if cause.judgment == "acceptable":
            return f"你确认实际约 {minutes} 分钟的通勤可以接受。"
    observation = cause.observation.rstrip("。")
    if cause.judgment == "unacceptable":
        return f"{observation}，并确认无法接受。"
    if cause.judgment == "acceptable":
        return f"{observation}，并确认可以接受。"
    return f"{observation}。"


def _format_challenge_cause(cause: ChallengeCause) -> str:
    if cause.kind == "TRADE_OFF":
        return "你对当前取舍提出了质疑，已重新评估。"
    if cause.kind == "PRIORITY":
        return "你质疑当前判断中过度强调某项条件，已重新评估。"
    if cause.kind == "ALTERNATIVE":
        return "你对当前推荐方向提出了不同选择，已重新评估。"
    return "你对当前判断提出了质疑，已重新评估。"


def _format_verification_outcome_cause(cause: VerificationOutcomeCause) -> str:
    if cause.status == "CONFIRMED":
        return "你已确认当前行动需要核实的信息，LiveOS 已据此重新评估。"
    if cause.status == "DISCONFIRMED":
        return "你已证伪当前行动需要核实的信息，LiveOS 已据此重新评估。"
    return "你完成了核实，但目前仍无法确认结果，LiveOS 已据此重新评估。"


def format_decision_change(causes: tuple[DecisionChangeCause, ...]) -> str:
    explanations: list[str] = []
    for cause in causes:
        if isinstance(cause, ProfileMutationCause):
            explanations.append(_format_profile_cause(cause))
        elif isinstance(cause, FeedbackCause):
            explanations.append(_format_feedback_cause(cause))
        elif isinstance(cause, ChallengeCause):
            explanations.append(_format_challenge_cause(cause))
        else:
            explanations.append(_format_verification_outcome_cause(cause))
    return "".join(explanations)


def decision_change_payload(
    causes: tuple[DecisionChangeCause, ...],
) -> dict[str, Any]:
    return {
        "causes": [asdict(cause) for cause in causes],
        "explanation": format_decision_change(causes),
    }


class DecisionChangeContext:
    def __init__(self) -> None:
        self._causes_by_conversation: dict[str, tuple[DecisionChangeCause, ...]] = {}
        self._lock = RLock()

    def set(
        self,
        conversation_id: str,
        causes: tuple[DecisionChangeCause, ...],
    ) -> None:
        with self._lock:
            if causes:
                self._causes_by_conversation[conversation_id] = causes
            else:
                self._causes_by_conversation.pop(conversation_id, None)

    def consume(self, conversation_id: str) -> tuple[DecisionChangeCause, ...]:
        with self._lock:
            return self._causes_by_conversation.pop(conversation_id, ())

    def clear(self, conversation_id: str) -> None:
        with self._lock:
            self._causes_by_conversation.pop(conversation_id, None)


decision_change_context = DecisionChangeContext()
