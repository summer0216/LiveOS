from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DecisionUnknownStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class DecisionUnknown(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    conversation_id: str
    property_id: str
    topic: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    status: DecisionUnknownStatus
    meaning: str = Field(min_length=1, max_length=500)
    created_at: datetime
    updated_at: datetime
