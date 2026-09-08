from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.api.ownership import anonymous_user_id, require_conversation_owner
from app.core.config import settings
from app.models.property import Property
from app.schemas.property import (
    PropertyCreateRequest,
    PropertyGeographicGroundingUpdate,
    PropertyGeographicResolutionResponse,
    PropertyListResponse,
    PropertyResponse,
)
from app.services.candidate_decision_state import project_candidate_decision_states
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_unknown_service import decision_unknown_service
from app.services.property_manager import property_manager

router = APIRouter(
    prefix="/properties",
    tags=["properties"],
)


class PropertyAnalyzeRequest(BaseModel):
    conversation_id: str
    description: str


class PropertyGeographicResolutionRequest(BaseModel):
    conversation_id: str
    context_location: str | None = None


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
    properties = property_manager.list(conversation_id)
    projections = project_candidate_decision_states(conversation_id, properties)
    open_unknowns = decision_unknown_service.list_open(conversation_id)
    unknowns_by_property = {
        property_.id: [
            unknown for unknown in open_unknowns if unknown.property_id == property_.id
        ]
        for property_ in properties
        if property_.id is not None
    }
    return PropertyListResponse(
        items=[
            PropertyResponse.model_validate(property_).model_copy(
                update={
                    "decision_state": projections[property_.id].state,
                    "state_reason": projections[property_.id].reason,
                    "unknowns": unknowns_by_property[property_.id],
                }
            )
            for property_ in properties
            if property_.id is not None
        ],
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


@router.patch(
    "/{property_id}/geography",
    response_model=PropertyResponse,
)
def update_property_geography(
    property_id: str,
    request: PropertyGeographicGroundingUpdate,
    raw_request: Request,
    response: Response,
) -> Property:
    require_conversation_owner(
        request.conversation_id, anonymous_user_id(raw_request, response)
    )
    property_ = property_manager.update_geographic_grounding(
        property_id,
        request.conversation_id,
        geographic_identity=request.geographic_identity,
        geographic_precision=request.geographic_precision,
        geographic_status=request.geographic_status,
        lng=request.lng,
        lat=request.lat,
    )
    if property_ is None:
        raise HTTPException(status_code=404, detail="Property not found.")
    return property_


@router.post(
    "/{property_id}/resolve-geography",
    response_model=PropertyGeographicResolutionResponse,
)
def resolve_property_geography(
    property_id: str,
    request: PropertyGeographicResolutionRequest,
    raw_request: Request,
    response: Response,
) -> PropertyGeographicResolutionResponse:
    require_conversation_owner(
        request.conversation_id, anonymous_user_id(raw_request, response)
    )
    result = property_manager.resolve_geographic_grounding(
        property_id,
        request.conversation_id,
        context_location=request.context_location,
        api_key=settings.AMAP_WEB_SERVICE_KEY,
    )
    property_ = property_manager.get_scoped(property_id, request.conversation_id)
    if property_ is None:
        raise HTTPException(status_code=404, detail="Property not found.")
    return PropertyGeographicResolutionResponse(
        property=PropertyResponse.model_validate(property_),
        status=result.status,
        ambiguous=result.ambiguous,
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
