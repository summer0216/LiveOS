from pydantic import BaseModel

from app.models.action_progress import CurrentActionProgress
from app.schemas.decision import DecisionResult
from app.schemas.profile import LivingProfileResponse


class LivingDecisionResumeResponse(BaseModel):
    conversation_id: str | None = None
    profile: LivingProfileResponse | None = None
    decision: DecisionResult | None = None
    action_progress: CurrentActionProgress | None = None
