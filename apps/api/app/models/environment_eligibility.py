from dataclasses import dataclass

from app.models.reality_evidence import RealityAdmission, RealityEvidence


@dataclass(frozen=True)
class EnvironmentAttention:
    conversation_id: str
    source_user_turn_id: int
    source_quote: str
    property_id: str
    property_identity: str
    property_lng: float
    property_lat: float
    category: str
    type_codes: tuple[str, ...]
    place_binding_source: str


@dataclass(frozen=True)
class EnvironmentProjectionEligibility:
    """Current-turn eligibility; it neither admits Reality nor changes Focus."""

    attention: EnvironmentAttention
    environment_external_id: str
    environment_identity: str
    environment_type_code: str
    evidence: RealityEvidence
    admission: RealityAdmission
    relevance_basis: str = "USER_EXPRESSED_CATEGORY"


@dataclass(frozen=True)
class EnvironmentEligibilityResult:
    conversation_id: str
    source_user_turn_id: int
    items: tuple[EnvironmentProjectionEligibility, ...] = ()
