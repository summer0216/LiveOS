from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActionProgressStatus(str, Enum):
    NOT_STARTED = "NOT_STARTED"
    PLANNED = "PLANNED"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class ActionProgressUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relevant: bool = False
    status: ActionProgressStatus | None = None

    @model_validator(mode="after")
    def validate_relevance(self) -> "ActionProgressUpdate":
        if self.relevant and self.status is None:
            raise ValueError("Relevant Action Progress requires a status.")
        if not self.relevant and self.status is not None:
            raise ValueError("Non-relevant Action Progress must not have a status.")
        return self


NO_ACTION_PROGRESS_UPDATE = ActionProgressUpdate()


class DecisionActionState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    conversation_id: str
    decision_record_id: str
    action_key: str = Field(min_length=1)
    next_text: str = Field(min_length=1)
    status: ActionProgressStatus | None = None
    created_at: datetime
    updated_at: datetime


class CurrentActionProgress(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    action_id: str | None = None
    next_text: str = Field(min_length=1)
    status: ActionProgressStatus | None = None
