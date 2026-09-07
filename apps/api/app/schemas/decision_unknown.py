from pydantic import BaseModel, ConfigDict

from app.models.decision_unknown import DecisionUnknownStatus


class DecisionUnknownResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    property_id: str
    topic: str
    status: DecisionUnknownStatus
    meaning: str
