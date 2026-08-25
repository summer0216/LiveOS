from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DecisionChallenge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    relevant: bool = False
    kind: Literal["DIRECT", "TRADE_OFF", "PRIORITY", "ALTERNATIVE"] | None = None
    subject: str | None = Field(default=None, max_length=120)
    statement: str | None = Field(default=None, max_length=240)
    target_property_id: str | None = Field(default=None, max_length=120)

    @model_validator(mode="after")
    def validate_relevance(self) -> "DecisionChallenge":
        if self.relevant:
            if self.kind is None or not self.statement or not self.statement.strip():
                raise ValueError(
                    "Relevant decision challenges require a kind and statement."
                )
            return self

        if any(
            value is not None
            for value in (
                self.kind,
                self.subject,
                self.statement,
                self.target_property_id,
            )
        ):
            raise ValueError("Non-relevant decision challenges must be empty.")
        return self


NO_DECISION_CHALLENGE = DecisionChallenge()
