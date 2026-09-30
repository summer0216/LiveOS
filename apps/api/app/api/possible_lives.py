from app.api.ownership import anonymous_user_id, require_conversation_owner
from app.schemas.possible_life import (
    LivingTimeReferenceResponse,
    PersonalMeaningReferenceResponse,
    PossibleLifeWorldStateListResponse,
    PossibleLifeWorldStateResponse,
    WorkSubjectReferenceResponse,
)
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.stores.runtime import (
    living_time_relationship_store,
    possible_life_store,
    work_subject_store,
)
from fastapi import APIRouter, Request, Response

router = APIRouter(prefix="/possible-lives", tags=["Possible Lives"])


@router.get("", response_model=PossibleLifeWorldStateListResponse)
def list_possible_life_world_state(
    conversation_id: str,
    request: Request,
    response: Response,
) -> PossibleLifeWorldStateListResponse:
    require_conversation_owner(conversation_id, anonymous_user_id(request, response))
    subject = work_subject_store.get(conversation_id)
    profile = profile_manager.get(conversation_id)
    if subject is None or profile is None or profile.commute_minutes is None:
        return PossibleLifeWorldStateListResponse()

    items: list[PossibleLifeWorldStateResponse] = []
    for possible_life in possible_life_store.list(conversation_id):
        residence = property_manager.get_scoped(
            possible_life.residence_property_id, conversation_id,
        )
        living_time = living_time_relationship_store.get(
            conversation_id, possible_life.living_time_residence_property_id,
        )
        if (
            residence is None
            or living_time is None
            or residence.id != possible_life.residence_property_id
            or living_time.residence_property_id
            != possible_life.living_time_residence_property_id
            or living_time.work_subject_identity != subject.identity
            or living_time.work_geographic_identity != subject.geographic_identity
        ):
            continue
        items.append(
            PossibleLifeWorldStateResponse(
                id=possible_life.id,
                work_subject_owner_id=possible_life.work_subject_owner_id,
                residence_property_id=possible_life.residence_property_id,
                living_time_residence_property_id=(
                    possible_life.living_time_residence_property_id
                ),
                personal_meaning_reference=(
                    possible_life.personal_meaning_reference
                ),
                work_subject=WorkSubjectReferenceResponse.model_validate(
                    subject, from_attributes=True,
                ),
                living_time=LivingTimeReferenceResponse.model_validate(
                    living_time, from_attributes=True,
                ),
                personal_meaning=PersonalMeaningReferenceResponse(
                    reference=possible_life.personal_meaning_reference,
                    maximum_commute_minutes=profile.commute_minutes,
                    satisfied=(
                        living_time.travel_minutes <= profile.commute_minutes
                    ),
                ),
            )
        )
    return PossibleLifeWorldStateListResponse(items=items)
