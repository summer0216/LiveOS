from dataclasses import dataclass

from app.models.property import CommuteMode


@dataclass(frozen=True)
class LivingTimeRelationship:
    residence_property_id: str
    residence_identity: str
    residence_geographic_identity: str
    work_subject_identity: str
    work_geographic_identity: str
    travel_minutes: int
    travel_mode: CommuteMode
    evidence_source: str
    evidence_reference: str


@dataclass(frozen=True)
class LivingTimeRequirementEvaluation:
    relationship: LivingTimeRelationship
    maximum_minutes: int
    satisfied: bool
