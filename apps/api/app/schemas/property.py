from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PropertyFields(BaseModel):
    title: str | None = None
    district: str | None = None
    rent: int | None = None
    area: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    commute_minutes: int | None = None
    pet_friendly: bool | None = None


class PropertyCreateRequest(PropertyFields):
    conversation_id: str = Field(min_length=1)


class PropertyResponse(PropertyFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    decision_state: Literal["ACTIVE", "WEAKENED", "REJECTED"] = "ACTIVE"
    state_reason: str | None = None


class PropertyListResponse(BaseModel):
    items: list[PropertyResponse] = Field(default_factory=list)
