from fastapi import APIRouter, HTTPException, Request, Response

from app.api.ownership import anonymous_user_id
from app.schemas.profile import LivingProfileResponse
from app.schemas.resume import LivingDecisionResumeResponse
from app.services.resume_resolver import ResumableLivingState, resume_resolver

router = APIRouter(
    prefix="/resume",
    tags=["Resume"],
)


def build_resume_response(
    state: ResumableLivingState | None,
) -> LivingDecisionResumeResponse:
    if state is None:
        return LivingDecisionResumeResponse()

    profile = state.profile
    return LivingDecisionResumeResponse(
        conversation_id=state.conversation_id,
        profile=(
            LivingProfileResponse(
                conversation_id=state.conversation_id,
                work_location=profile.work_location,
                budget=profile.budget,
                commute_minutes=profile.commute_minutes,
                preferred_city=profile.preferred_city,
                family_size=profile.family_size,
                has_pet=profile.has_pet,
                latest_insights=profile.latest_insights,
                preference_tags=profile.preference_tags,
            )
            if profile is not None
            else None
        ),
        decision=state.decision,
    )


@router.get("", response_model=LivingDecisionResumeResponse)
def get_resumable_living_state(
    request: Request,
    response: Response,
    conversation_id: str | None = None,
) -> LivingDecisionResumeResponse:
    owner_id = anonymous_user_id(request, response)
    if conversation_id is None:
        return build_resume_response(resume_resolver.resolve_for_owner(owner_id))

    state = resume_resolver.resolve_conversation(owner_id, conversation_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return build_resume_response(state)
