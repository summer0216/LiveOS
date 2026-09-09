from pydantic import BaseModel, Field


class CurrentGeographicReality(BaseModel):
    lng: float = Field(ge=-180, le=180)
    lat: float = Field(ge=-90, le=90)


class ChatRequest(BaseModel):
    conversation_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    current_geographic_reality: CurrentGeographicReality | None = None


class ChatResponse(BaseModel):
    reply: str
