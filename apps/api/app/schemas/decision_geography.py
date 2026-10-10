from pydantic import BaseModel

from app.models.property import GeographicPrecision


class DecisionGeographyResponse(BaseModel):
    conversation_id: str
    intent_established: bool
    intent_type: str | None = None
    identity: str
    identity_source: str | None = None
    geographic_scope: str | None = None
    geographic_identity: str | None = None
    geographic_precision: GeographicPrecision | None = None
    status: str
    lng: float | None = None
    lat: float | None = None
    source_user_turn_id: str | None = None
