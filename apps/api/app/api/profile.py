from fastapi import APIRouter, HTTPException, Request, Response

from app.api.ownership import anonymous_user_id, require_conversation_owner
from app.models.profile import LivingProfile
from app.schemas.profile import (
    LivingProfileResponse,
    PreferenceTagsUpdateRequest,
)
from app.services.profile_manager import profile_manager

router = APIRouter(
    prefix="/profiles",
    tags=["Profiles"],
)


def build_profile_response(
    conversation_id: str,
    profile: LivingProfile,
) -> LivingProfileResponse:
    return LivingProfileResponse(
        conversation_id=conversation_id,
        work_location=profile.work_location,
        budget=profile.budget,
        commute_minutes=profile.commute_minutes,
        preferred_city=profile.preferred_city,
        family_size=profile.family_size,
        has_pet=profile.has_pet,
        latest_insights=profile.latest_insights,
        preference_tags=profile.preference_tags,
    )


@router.get(
    "/{conversation_id}",
    response_model=LivingProfileResponse,
)
async def get_living_profile(
    conversation_id: str,
    request: Request,
    response: Response,
) -> LivingProfileResponse:
    require_conversation_owner(conversation_id, anonymous_user_id(request, response))
    profile = profile_manager.get(conversation_id)

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Living profile not found.",
        )

    return build_profile_response(
        conversation_id=conversation_id,
        profile=profile,
    )


@router.patch(
    "/{conversation_id}/tags",
    response_model=LivingProfileResponse,
)
async def update_preference_tags(
    conversation_id: str,
    request: PreferenceTagsUpdateRequest,
    raw_request: Request,
    response: Response,
) -> LivingProfileResponse:
    require_conversation_owner(
        conversation_id, anonymous_user_id(raw_request, response)
    )
    profile = profile_manager.update_tags(
        conversation_id=conversation_id,
        preference_tags=request.preference_tags,
    )

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Living profile not found.",
        )

    return build_profile_response(
        conversation_id=conversation_id,
        profile=profile,
    )
