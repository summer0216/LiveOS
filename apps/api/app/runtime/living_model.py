from pydantic import BaseModel, ConfigDict, Field

from app.runtime.memory_context import DecisionMemoryContextItem


class LivingModelProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    work_location: str | None = None
    budget: int | None = None
    commute_minutes: int | None = None
    preferred_city: str | None = None
    family_size: int | None = None
    has_pet: bool | None = None


class LivingModel(BaseModel):
    model_config = ConfigDict(frozen=True)

    conversation_id: str
    profile: LivingModelProfile = Field(
        default_factory=LivingModelProfile,
    )
    decision_memory: list[DecisionMemoryContextItem] = Field(
        default_factory=list,
    )


def empty_living_model(conversation_id: str) -> LivingModel:
    return LivingModel(
        conversation_id=conversation_id.strip(),
        profile=LivingModelProfile(),
        decision_memory=[],
    )
