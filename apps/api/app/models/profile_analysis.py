from pydantic import BaseModel, Field

from app.models.decision_feedback import (
    NO_DECISION_FEEDBACK,
    DecisionRelevantFeedback,
)
from app.models.profile_patch import LivingProfilePatch


class ProfileAnalysis(BaseModel):
    patch: LivingProfilePatch
    insights: list[str] = Field(default_factory=list)
    decision_feedback: DecisionRelevantFeedback = Field(
        default_factory=lambda: NO_DECISION_FEEDBACK,
    )
