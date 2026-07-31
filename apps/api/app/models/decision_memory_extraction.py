from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.models.decision_memory import DecisionMemory


class DecisionMemoryExtractionStatus(str, Enum):
    COMPLETED = "completed"
    INSUFFICIENT_HISTORY = "insufficient_history"
    FAILED = "failed"


class DecisionMemoryExtractionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidates: list[object] = Field(max_length=5)


class DecisionMemoryExtractionResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    conversation_id: str
    status: DecisionMemoryExtractionStatus
    history_record_count: int
    candidate_count: int
    saved_count: int
    rejected_count: int
    memories: list[DecisionMemory] = Field(default_factory=list)
