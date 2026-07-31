from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.decision_memory import DecisionMemoryCategory
from app.models.decision_memory_extraction import (
    DecisionMemoryExtractionStatus,
)


class DecisionMemoryResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: UUID
    conversation_id: str
    category: DecisionMemoryCategory
    content: str
    confidence: float
    evidence_record_ids: list[UUID]
    evidence_count: int
    created_at: datetime
    updated_at: datetime


class DecisionMemoryListResponse(BaseModel):
    conversation_id: str
    memories: list[DecisionMemoryResponse] = Field(default_factory=list)


class DecisionMemoryRefreshResponse(BaseModel):
    conversation_id: str
    status: DecisionMemoryExtractionStatus
    history_record_count: int
    candidate_count: int
    saved_count: int
    rejected_count: int
    memories: list[DecisionMemoryResponse] = Field(default_factory=list)
