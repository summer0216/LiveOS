from fastapi import APIRouter, Request, Response

from app.api.ownership import anonymous_user_id, require_conversation_owner
from app.schemas.decision_geography import DecisionGeographyResponse
from app.services.decision_geography_service import decision_geography_service

router = APIRouter(prefix="/decision-geography", tags=["Decision Geography"])


@router.get("", response_model=DecisionGeographyResponse | None)
def get_decision_geography(
    conversation_id: str,
    request: Request,
    response: Response,
) -> DecisionGeographyResponse | None:
    require_conversation_owner(conversation_id, anonymous_user_id(request, response))
    state = decision_geography_service.get(conversation_id)
    if state is None:
        return None
    return DecisionGeographyResponse(
        conversation_id=conversation_id,
        intent_established=state.intent_established,
        intent_type=state.intent_type,
        identity=state.identity or "",
        status=state.status,
        lng=state.lng,
        lat=state.lat,
    )
