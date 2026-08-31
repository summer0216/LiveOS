from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.action_progress import VerificationOutcomeStatus


class DecisionMemoryCategory(str, Enum):
    PRIORITY = "priority"
    PREFERENCE = "preference"
    CONSTRAINT = "constraint"
    TRADE_OFF = "trade_off"
    EVIDENCE_RELIABILITY = "evidence_reliability"


class DecisionMemoryCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: DecisionMemoryCategory
    content: str = Field(max_length=500)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_record_ids: list[UUID]


class DecisionMemory(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    conversation_id: str
    category: DecisionMemoryCategory
    content: str
    normalized_content: str
    confidence: float
    evidence_record_ids: list[UUID]
    source_action_id: UUID | None = None
    source_action_key: str | None = None
    source_outcome_status: VerificationOutcomeStatus | None = None
    source_decision_record_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
