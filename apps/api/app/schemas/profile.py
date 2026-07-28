from pydantic import BaseModel


class LivingProfileResponse(BaseModel):
    conversation_id: str
    work_location: str | None = None
    budget: int | None = None
    commute_minutes: int | None = None
    preferred_city: str | None = None
    family_size: int | None = None
    has_pet: bool | None = None

    latest_insights: list[str] = []
