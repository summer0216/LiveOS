from pydantic import BaseModel, Field

from app.models.action_progress import (
    NO_ACTION_PROGRESS_UPDATE,
    NO_VERIFICATION_OUTCOME_UPDATE,
    ActionProgressUpdate,
    VerificationOutcomeUpdate,
)
from app.models.decision_challenge import (
    NO_DECISION_CHALLENGE,
    DecisionChallenge,
)
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
    decision_challenge: DecisionChallenge = Field(
        default_factory=lambda: NO_DECISION_CHALLENGE,
    )
    action_progress_update: ActionProgressUpdate = Field(
        default_factory=lambda: NO_ACTION_PROGRESS_UPDATE,
    )
    verification_outcome_update: VerificationOutcomeUpdate = Field(
        default_factory=lambda: NO_VERIFICATION_OUTCOME_UPDATE,
    )
