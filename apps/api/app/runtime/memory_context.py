from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.decision_memory import DecisionMemoryCategory


class DecisionMemoryContextItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: DecisionMemoryCategory
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_count: int = Field(ge=0)
    updated_at: datetime


class DecisionMemoryContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    conversation_id: str
    memories: list[DecisionMemoryContextItem] = Field(default_factory=list)
