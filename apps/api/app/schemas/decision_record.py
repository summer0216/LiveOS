from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.decision import DecisionReason, DecisionTradeOff


class DecisionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    conversation_id: str
    created_at: datetime
    summary: str
    best_property_id: str
    reasons: list[DecisionReason]
    trade_offs: list[DecisionTradeOff]
    confidence: float | None


class DecisionHistoryResponse(BaseModel):
    conversation_id: str
    items: list[DecisionRecord] = Field(default_factory=list)
    total: int
