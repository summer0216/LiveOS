from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.ownership import anonymous_user_id, require_conversation_owner
from app.models.property import Property
from app.schemas.property import (
    PropertyCreateRequest,
    PropertyListResponse,
    PropertyResponse,
)
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
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
    raw_request: Request,
    response: Response,
) -> Property:
    require_conversation_owner(
        request.conversation_id, anonymous_user_id(raw_request, response)
    )
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
    request: Request,
    response: Response,
) -> PropertyListResponse:
    require_conversation_owner(conversation_id, anonymous_user_id(request, response))
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
    raw_request: Request,
    response: Response,
) -> Property:
    user_id = anonymous_user_id(raw_request, response)
    conversation_manager.get_or_create(request.conversation_id, user_id)
    require_conversation_owner(request.conversation_id, user_id)
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
    request: Request,
    response: Response,
) -> None:
    if not property_manager.delete_for_owner(
        property_id, anonymous_user_id(request, response)
    ):
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
    request: Request,
    response: Response,
) -> Property:
    require_conversation_owner(conversation_id, anonymous_user_id(request, response))
    property_ = property_manager.get(
        conversation_id,
    )

    if property_ is None:
        raise HTTPException(
            status_code=404,
            detail="Property not found.",
        )

    return property_
