from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.property import Property
from app.services.chat_service import chat_service
from app.services.property_manager import property_manager

router = APIRouter(
    prefix="/properties",
    tags=["properties"],
)


class PropertyAnalyzeRequest(BaseModel):
    conversation_id: str
    description: str


@router.post(
    "/analyze",
    response_model=Property,
)
def analyze_property(
    request: PropertyAnalyzeRequest,
) -> Property:
    return chat_service.update_property(
        conversation_id=request.conversation_id,
        description=request.description,
    )


@router.get(
    "/{conversation_id}",
    response_model=Property,
)
def get_property(
    conversation_id: str,
) -> Property:
    property_ = property_manager.get(
        conversation_id,
    )

    if property_ is None:
        raise HTTPException(
            status_code=404,
            detail="Property not found.",
        )

    return property_
