from pydantic import BaseModel, ConfigDict, Field

from app.schemas.decision_record import DecisionRecord


class DecisionContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    conversation_id: str
    recent_decisions: list[DecisionRecord] = Field(default_factory=list)
