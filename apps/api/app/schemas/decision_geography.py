from pydantic import BaseModel


class DecisionGeographyResponse(BaseModel):
    conversation_id: str
    intent_established: bool
    intent_type: str | None = None
    identity: str
    identity_source: str | None = None
    geographic_scope: str | None = None
    status: str
    lng: float | None = None
    lat: float | None = None
