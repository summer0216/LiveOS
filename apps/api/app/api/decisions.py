from fastapi import APIRouter

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
) -> DecisionResult:
    return decision_service.generate(conversation_id)
