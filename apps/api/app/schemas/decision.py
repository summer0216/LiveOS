from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.runtime.living_model import LivingModel


class DecisionReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class DecisionTradeOff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class DecisionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["waiting", "ready"]
    summary: str | None = None
    best_property_id: str | None = None
    reasons: list[DecisionReason] = Field(default_factory=list, max_length=4)
    trade_offs: list[DecisionTradeOff] = Field(
        default_factory=list,
        max_length=3,
    )
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_status_fields(self) -> "DecisionResult":
        if self.status == "waiting":
            if self.best_property_id is not None:
                raise ValueError(
                    "Waiting decisions cannot include a best property.",
                )
            if self.reasons or self.trade_offs or self.confidence is not None:
                raise ValueError(
                    "Waiting decisions cannot include recommendation details.",
                )
            return self

        if not self.summary or not self.summary.strip():
            raise ValueError("Ready decisions require a summary.")

        if not self.best_property_id:
            raise ValueError("Ready decisions require a best property.")

        if not self.reasons:
            raise ValueError("Ready decisions require at least one reason.")

        return self


class PropertyDecisionInput(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: str
    title: str | None = None
    district: str | None = None
    rent: int | None = None
    area: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    commute_minutes: int | None = None
    pet_friendly: bool | None = None


class DecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    living_model: LivingModel
    properties: list[PropertyDecisionInput]
