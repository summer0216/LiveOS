from pydantic import BaseModel

from app.schemas.decision import DecisionResult
from app.schemas.profile import LivingProfileResponse


class LivingDecisionResumeResponse(BaseModel):
    conversation_id: str | None = None
    profile: LivingProfileResponse | None = None
    decision: DecisionResult | None = None
