from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.property import Property
from app.schemas.property import (
    PropertyCreateRequest,
    PropertyListResponse,
    PropertyResponse,
)
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
    response_model=PropertyResponse,
)
def analyze_property(
    request: PropertyAnalyzeRequest,
) -> Property:
    return chat_service.update_property(
        conversation_id=request.conversation_id,
        description=request.description,
    )


@router.get(
    "",
    response_model=PropertyListResponse,
)
def list_properties(
    conversation_id: str,
) -> PropertyListResponse:
    return PropertyListResponse(
        items=property_manager.list(conversation_id),
    )


@router.post(
    "",
    response_model=PropertyResponse,
    status_code=201,
)
def create_property(
    request: PropertyCreateRequest,
) -> Property:
    return property_manager.create(
        conversation_id=request.conversation_id,
        property_=Property(
            title=request.title,
            district=request.district,
            rent=request.rent,
            area=request.area,
            bedrooms=request.bedrooms,
            bathrooms=request.bathrooms,
            commute_minutes=request.commute_minutes,
            pet_friendly=request.pet_friendly,
        ),
    )


@router.delete(
    "/{property_id}",
    status_code=204,
)
def delete_property(
    property_id: str,
) -> None:
    if not property_manager.delete(property_id):
        raise HTTPException(
            status_code=404,
            detail="Property not found.",
        )


@router.get(
    "/{conversation_id}",
    response_model=PropertyResponse,
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
