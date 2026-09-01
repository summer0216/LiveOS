import re
from dataclasses import dataclass
from typing import Literal

from app.models.action_progress import (
    LatestVerifiedAction,
    VerificationEvidence,
    VerificationOutcomeStatus,
)
from app.models.profile import LivingProfile
from app.models.property import Property
from app.services.decision_action_progress import decision_action_progress_service
from app.services.decision_record_service import decision_record_service
from app.services.profile_manager import profile_manager

CandidateDecisionState = Literal["ACTIVE", "WEAKENED", "REJECTED"]


@dataclass(frozen=True)
class CandidateDecisionProjection:
    state: CandidateDecisionState
    reason: str | None = None


ACTIVE_PROJECTION = CandidateDecisionProjection(state="ACTIVE")


def _numeric_value(evidence: VerificationEvidence) -> int | None:
    if isinstance(evidence.value, int):
        return evidence.value
    match = re.search(r"\d+", evidence.value)
    return int(match.group()) if match is not None else None


def _violates_current_constraint(
    evidence: VerificationEvidence,
    profile: LivingProfile | None,
) -> bool:
    if profile is None:
        return False
    if evidence.field == "commute_minutes" and profile.commute_minutes is not None:
        value = _numeric_value(evidence)
        return value is not None and value > profile.commute_minutes
    if evidence.field == "rent" and profile.budget is not None:
        value = _numeric_value(evidence)
        return value is not None and value > profile.budget
    if evidence.field == "city" and profile.preferred_city:
        return str(evidence.value).strip() != profile.preferred_city.strip()
    return False


def _projection_from_verification(
    verification: LatestVerifiedAction,
    profile: LivingProfile | None,
) -> CandidateDecisionProjection:
    grounded_evidence = tuple(
        evidence
        for evidence in verification.verification_evidence
        if evidence.field in {"commute_minutes", "rent", "city"}
    )
    if not grounded_evidence:
        return ACTIVE_PROJECTION

    reason = grounded_evidence[0].statement
    if verification.outcome_status == VerificationOutcomeStatus.INCONCLUSIVE:
        return CandidateDecisionProjection(state="WEAKENED", reason=reason)
    if verification.outcome_status == VerificationOutcomeStatus.DISCONFIRMED:
        state: CandidateDecisionState = (
            "REJECTED"
            if any(
                _violates_current_constraint(evidence, profile)
                for evidence in grounded_evidence
            )
            else "WEAKENED"
        )
        return CandidateDecisionProjection(state=state, reason=reason)
    return ACTIVE_PROJECTION


def project_candidate_decision_states(
    conversation_id: str,
    properties: list[Property],
) -> dict[str, CandidateDecisionProjection]:
    projections = {
        property_.id: ACTIVE_PROJECTION
        for property_ in properties
        if property_.id is not None
    }
    verification = decision_action_progress_service.latest_verified_state(
        conversation_id
    )
    if verification is None:
        return projections

    source_decision = decision_record_service.get_by_id(
        conversation_id,
        verification.decision_record_id,
    )
    if (
        source_decision is None
        or source_decision.best_property_id not in projections
    ):
        return projections

    projections[source_decision.best_property_id] = _projection_from_verification(
        verification,
        profile_manager.get(conversation_id),
    )
    return projections
