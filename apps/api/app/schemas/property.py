from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    PropertyProvenance,
    PropertyRentSource,
)
from app.schemas.decision_unknown import DecisionUnknownResponse


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


class PropertyGeographicGroundingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    conversation_id: str = Field(min_length=1)
    geographic_identity: str | None = Field(default=None, min_length=1)
    geographic_precision: GeographicPrecision | None = None
    geographic_status: GeographicStatus = GeographicStatus.UNRESOLVED
    lng: float | None = Field(default=None, ge=-180, le=180)
    lat: float | None = Field(default=None, ge=-90, le=90)

    @model_validator(mode="after")
    def validate_grounding(self) -> "PropertyGeographicGroundingUpdate":
        if self.geographic_status == GeographicStatus.GROUNDED:
            if (
                self.geographic_identity is None
                or self.geographic_precision is None
                or self.lng is None
                or self.lat is None
            ):
                raise ValueError(
                    "Grounded property requires identity, precision, lng, and lat."
                )
        elif self.lng is not None or self.lat is not None:
            raise ValueError("Unresolved property must not contain coordinates.")
        return self


class PropertyResponse(PropertyFields):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    decision_state: Literal["ACTIVE", "WEAKENED", "REJECTED"] = "ACTIVE"
    state_reason: str | None = None
    unknowns: list[DecisionUnknownResponse] = Field(default_factory=list)
    geographic_identity: str | None = None
    geographic_precision: GeographicPrecision | None = None
    geographic_status: GeographicStatus = GeographicStatus.UNRESOLVED
    lng: float | None = None
    lat: float | None = None
    provenance: PropertyProvenance = PropertyProvenance.USER_PROVIDED
    external_id: str | None = None
    commute_mode: CommuteMode | None = None
    rent_source: PropertyRentSource | None = None


class PropertyListResponse(BaseModel):
    items: list[PropertyResponse] = Field(default_factory=list)


class PropertyGeographicResolutionResponse(BaseModel):
    property: PropertyResponse
    status: Literal["GROUNDED", "UNRESOLVED"]
    ambiguous: bool = False
