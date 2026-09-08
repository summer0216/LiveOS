from pydantic import BaseModel, Field, model_validator

from app.models.property import GeographicPrecision


class GeographicClarification(BaseModel):
    relevant: bool = False
    target_property_id: str | None = Field(default=None, min_length=1)
    geographic_identity: str | None = Field(default=None, min_length=1)
    geographic_precision: GeographicPrecision | None = None
    lng: float | None = Field(default=None, ge=-180, le=180)
    lat: float | None = Field(default=None, ge=-90, le=90)

    @model_validator(mode="after")
    def validate_grounding(self) -> "GeographicClarification":
        if not self.relevant:
            return self
        if (
            self.target_property_id is None
            or self.geographic_identity is None
            or self.geographic_precision is None
            or self.lng is None
            or self.lat is None
        ):
            raise ValueError(
                "Relevant geographic clarification requires a complete grounding."
            )
        return self


NO_GEOGRAPHIC_CLARIFICATION = GeographicClarification()
