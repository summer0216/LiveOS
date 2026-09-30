from dataclasses import dataclass

from app.models.living_time import (
    LivingTimeRelationship,
    LivingTimeRequirementEvaluation,
)
from app.models.property import GeographicStatus, Property
from app.models.work_subject import WorkSubject
from app.services.transit_duration import (
    LivingTimeResult,
    TransitDurationService,
    transit_duration_service,
)
from app.stores.persistent import LivingTimeRelationshipStore
from app.stores.runtime import living_time_relationship_store, work_subject_store


@dataclass(frozen=True)
class LivingTimeAdmission:
    relationship: LivingTimeRelationship
    requirement: LivingTimeRequirementEvaluation | None


class LivingTimeRelationshipService:
    def __init__(
        self,
        *,
        relationships: LivingTimeRelationshipStore = living_time_relationship_store,
        transit: TransitDurationService = transit_duration_service,
    ) -> None:
        self._relationships = relationships
        self._transit = transit

    def establish(
        self,
        *,
        conversation_id: str,
        residence: Property,
        work_subject: WorkSubject,
        api_key: str | None,
        commute_requirement_minutes: int | None = None,
    ) -> LivingTimeAdmission | None:
        if not self._valid_endpoints(residence, work_subject):
            return None
        route = self._transit.calculate_living_time(
            origin_lng=residence.lng,
            origin_lat=residence.lat,
            destination_lng=work_subject.lng,
            destination_lat=work_subject.lat,
            api_key=api_key,
        )
        return self.admit_route_evidence(
            conversation_id=conversation_id,
            residence=residence,
            work_subject=work_subject,
            route=route,
            commute_requirement_minutes=commute_requirement_minutes,
        )

    def establish_for_authoritative_work(
        self,
        *,
        conversation_id: str,
        residence: Property,
        api_key: str | None,
        commute_requirement_minutes: int | None = None,
    ) -> LivingTimeAdmission | None:
        subject = work_subject_store.get(conversation_id)
        if subject is None:
            return None
        return self.establish(
            conversation_id=conversation_id,
            residence=residence,
            work_subject=subject,
            api_key=api_key,
            commute_requirement_minutes=commute_requirement_minutes,
        )

    def admit_route_evidence(
        self,
        *,
        conversation_id: str,
        residence: Property,
        work_subject: WorkSubject,
        route: LivingTimeResult | None,
        commute_requirement_minutes: int | None = None,
    ) -> LivingTimeAdmission | None:
        if (
            not self._valid_endpoints(residence, work_subject)
            or route is None
            or route.minutes < 1
            or not route.evidence_source
            or not route.evidence_reference
        ):
            return None
        relationship = self._relationships.save(
            conversation_id,
            LivingTimeRelationship(
                residence_property_id=residence.id or "",
                residence_identity=residence.title or "",
                residence_geographic_identity=residence.geographic_identity or "",
                work_subject_identity=work_subject.identity,
                work_geographic_identity=work_subject.geographic_identity,
                travel_minutes=route.minutes,
                travel_mode=route.mode,
                evidence_source=route.evidence_source,
                evidence_reference=route.evidence_reference,
            ),
        )
        requirement = (
            LivingTimeRequirementEvaluation(
                relationship=relationship,
                maximum_minutes=commute_requirement_minutes,
                satisfied=relationship.travel_minutes <= commute_requirement_minutes,
            )
            if commute_requirement_minutes is not None
            and commute_requirement_minutes > 0
            else None
        )
        admission = LivingTimeAdmission(relationship, requirement)
        if requirement is not None:
            from app.services.possible_life_admission import (
                possible_life_admission_service,
            )

            possible_life_admission_service.admit(
                conversation_id, residence.id or "",
            )
        return admission

    def admit_for_authoritative_work(
        self,
        *,
        conversation_id: str,
        residence: Property,
        route: LivingTimeResult | None,
        commute_requirement_minutes: int | None = None,
    ) -> LivingTimeAdmission | None:
        subject = work_subject_store.get(conversation_id)
        if subject is None:
            return None
        return self.admit_route_evidence(
            conversation_id=conversation_id,
            residence=residence,
            work_subject=subject,
            route=route,
            commute_requirement_minutes=commute_requirement_minutes,
        )

    @staticmethod
    def _valid_endpoints(residence: Property, work_subject: WorkSubject) -> bool:
        return bool(
            residence.id
            and residence.title
            and residence.geographic_status == GeographicStatus.GROUNDED
            and residence.geographic_identity
            and residence.lng is not None
            and residence.lat is not None
            and work_subject.geographic_status == "GROUNDED"
            and work_subject.geographic_precision == "PLACE"
            and work_subject.geographic_identity
        )


living_time_relationship_service = LivingTimeRelationshipService()
