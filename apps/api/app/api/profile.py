from fastapi import APIRouter, HTTPException

from app.schemas.profile import LivingProfileResponse
from app.services.profile_manager import profile_manager

router = APIRouter(
    prefix="/profiles",
    tags=["Profiles"],
)


@router.get(
    "/{conversation_id}",
    response_model=LivingProfileResponse,
)
async def get_living_profile(
    conversation_id: str,
) -> LivingProfileResponse:
    profile = profile_manager.get(conversation_id)

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Living profile not found.",
        )

    return LivingProfileResponse(
        conversation_id=conversation_id,
        work_location=profile.work_location,
        budget=profile.budget,
        commute_minutes=profile.commute_minutes,
        preferred_city=profile.preferred_city,
        family_size=profile.family_size,
        has_pet=profile.has_pet,
    )
