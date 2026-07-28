from pydantic import BaseModel, Field

from app.models.profile_patch import LivingProfilePatch


class ProfileAnalysis(BaseModel):
    patch: LivingProfilePatch
    insights: list[str] = Field(default_factory=list)
