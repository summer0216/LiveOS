from typing import Literal

from app.models.property import CommuteMode
from pydantic import BaseModel, Field


class WorkSubjectReferenceResponse(BaseModel):
    identity: str
    geographic_identity: str
    geographic_precision: Literal["PLACE"]
    geographic_status: Literal["GROUNDED"]
    lng: float
    lat: float
    relationship: Literal["WORK"]


class LivingTimeReferenceResponse(BaseModel):
    residence_property_id: str
    residence_identity: str
    residence_geographic_identity: str
    work_subject_identity: str
    work_geographic_identity: str
    travel_minutes: int
    travel_mode: CommuteMode
    evidence_source: str
    evidence_reference: str


class PersonalMeaningReferenceResponse(BaseModel):
    reference: str
    maximum_commute_minutes: int
    satisfied: bool


class PossibleLifeWorldStateResponse(BaseModel):
    id: str
    work_subject_owner_id: str
    residence_property_id: str
    living_time_residence_property_id: str
    personal_meaning_reference: str
    work_subject: WorkSubjectReferenceResponse
    living_time: LivingTimeReferenceResponse
    personal_meaning: PersonalMeaningReferenceResponse


class PossibleLifeWorldStateListResponse(BaseModel):
    items: list[PossibleLifeWorldStateResponse] = Field(default_factory=list)
