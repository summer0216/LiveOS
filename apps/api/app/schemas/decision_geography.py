from pydantic import BaseModel


class DecisionGeographyResponse(BaseModel):
    conversation_id: str
    intent_established: bool
    intent_type: str | None = None
    identity: str
    status: str
    lng: float | None = None
    lat: float | None = None
