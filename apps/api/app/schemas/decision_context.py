from pydantic import BaseModel, ConfigDict, Field

from app.models.action_progress import CurrentActionProgress
from app.models.decision_challenge import DecisionChallenge
from app.models.decision_feedback import DecisionRelevantFeedback
from app.runtime.memory_context import DecisionMemoryContext
from app.schemas.decision_record import DecisionRecord


def empty_memory_context() -> DecisionMemoryContext:
    return DecisionMemoryContext(
        conversation_id="",
        memories=[],
    )


class DecisionContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    conversation_id: str
    recent_decisions: list[DecisionRecord] = Field(default_factory=list)
    memory_context: DecisionMemoryContext = Field(
        default_factory=empty_memory_context,
    )
    current_feedback: DecisionRelevantFeedback | None = None
    current_challenge: DecisionChallenge | None = None
    current_action: CurrentActionProgress | None = None
