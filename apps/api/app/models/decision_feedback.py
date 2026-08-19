from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DecisionRelevantFeedback(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    relevant: bool = False
    observation: str | None = Field(default=None, max_length=500)
    judgment: Literal["acceptable", "unacceptable"] | None = None
    observed_commute_minutes: int | None = Field(default=None, ge=0, le=1440)

    @model_validator(mode="after")
    def validate_relevance(self) -> "DecisionRelevantFeedback":
        if not self.relevant and any(
            value is not None
            for value in (
                self.observation,
                self.judgment,
                self.observed_commute_minutes,
            )
        ):
            raise ValueError("Non-relevant feedback cannot include decision meaning.")
        if self.relevant and not self.observation:
            raise ValueError("Relevant feedback requires a bounded observation.")
        return self


NO_DECISION_FEEDBACK = DecisionRelevantFeedback()
