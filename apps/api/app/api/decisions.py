from fastapi import APIRouter, Request, Response

from app.api.ownership import anonymous_user_id, require_conversation_owner
from app.schemas.decision import DecisionResult
from app.services.decision_service import decision_service

router = APIRouter(
    prefix="/decisions",
    tags=["Decisions"],
)


@router.get(
    "",
    response_model=DecisionResult,
)
def get_decision(
    conversation_id: str,
    request: Request,
    response: Response,
) -> DecisionResult:
    require_conversation_owner(conversation_id, anonymous_user_id(request, response))
    return decision_service.generate(conversation_id)
