from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any


def _aware_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class RealityEvidence:
    """Shared source, identity, and observation-time evidence contract."""

    source_provider: str
    source_reference: str
    identity: str
    observed_at: str
    source_record_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def qualifies(self, *, expected_identity: str | None = None) -> bool:
        observed = _aware_time(self.observed_at)
        return bool(
            isinstance(self.source_provider, str)
            and self.source_provider.strip()
            and isinstance(self.source_reference, str)
            and self.source_reference.strip()
            and isinstance(self.identity, str)
            and self.identity.strip()
            and (
                self.source_record_id is None
                or (
                    isinstance(self.source_record_id, str)
                    and self.source_record_id.strip()
                )
            )
            and observed is not None
            and observed <= datetime.now(UTC)
            and (
                expected_identity is None
                or self.identity == expected_identity
            )
        )

    @classmethod
    def from_mapping(cls, value: object) -> RealityEvidence | None:
        if not isinstance(value, Mapping):
            return None
        source_provider = value.get("source_provider")
        source_reference = value.get("source_reference")
        identity = value.get("identity")
        observed_at = value.get("observed_at")
        source_record_id = value.get("source_record_id")
        if not all(isinstance(item, str) for item in (
            source_provider, source_reference, identity, observed_at,
        )):
            return None
        if source_record_id is not None and not isinstance(source_record_id, str):
            return None
        return cls(
            source_provider=source_provider,
            source_reference=source_reference,
            identity=identity,
            observed_at=observed_at,
            source_record_id=source_record_id,
        )


@dataclass(frozen=True)
class RealityAdmission:
    """A durable decision binding evidence to the grounded Property world."""

    status: str
    admitted_at: str
    property_id: str
    property_identity: str
    property_lng: float
    property_lat: float
    evidence_reference: str
    evidence_observed_at: str
    authority: str

    def qualifies_for(
        self,
        *,
        property_id: str,
        property_identity: str,
        property_lng: float,
        property_lat: float,
        evidence: RealityEvidence,
    ) -> bool:
        admitted = _aware_time(self.admitted_at)
        observed = _aware_time(evidence.observed_at)
        return bool(
            self.status == "ADMITTED"
            and self.property_id == property_id
            and self.property_identity == property_identity
            and self.property_lng == property_lng
            and self.property_lat == property_lat
            and self.evidence_reference == evidence.source_reference
            and self.evidence_observed_at == evidence.observed_at
            and self.authority.strip()
            and admitted is not None
            and observed is not None
            and observed <= admitted <= datetime.now(UTC)
        )

    @classmethod
    def admit(
        cls,
        evidence: RealityEvidence,
        *,
        property_id: str,
        property_identity: str,
        property_lng: float,
        property_lat: float,
        authority: str,
        admitted_at: str | None = None,
    ) -> RealityAdmission | None:
        if (
            not evidence.qualifies()
            or not property_id.strip()
            or not property_identity.strip()
            or isinstance(property_lng, bool)
            or not isinstance(property_lng, (int, float))
            or isinstance(property_lat, bool)
            or not isinstance(property_lat, (int, float))
            or not (-180 <= property_lng <= 180)
            or not (-90 <= property_lat <= 90)
            or not authority.strip()
        ):
            return None
        admission = cls(
            status="ADMITTED",
            admitted_at=admitted_at or datetime.now(UTC).isoformat(),
            property_id=property_id,
            property_identity=property_identity,
            property_lng=property_lng,
            property_lat=property_lat,
            evidence_reference=evidence.source_reference,
            evidence_observed_at=evidence.observed_at,
            authority=authority,
        )
        if not admission.qualifies_for(
            property_id=property_id,
            property_identity=property_identity,
            property_lng=property_lng,
            property_lat=property_lat,
            evidence=evidence,
        ):
            return None
        return admission

    @classmethod
    def from_mapping(cls, value: object) -> RealityAdmission | None:
        if not isinstance(value, Mapping):
            return None
        try:
            admission = cls(
                status=value["status"],
                admitted_at=value["admitted_at"],
                property_id=value["property_id"],
                property_identity=value["property_identity"],
                property_lng=value["property_lng"],
                property_lat=value["property_lat"],
                evidence_reference=value["evidence_reference"],
                evidence_observed_at=value["evidence_observed_at"],
                authority=value["authority"],
            )
        except (KeyError, TypeError):
            return None
        if not all(isinstance(item, str) for item in (
            admission.status,
            admission.admitted_at,
            admission.property_id,
            admission.property_identity,
            admission.evidence_reference,
            admission.evidence_observed_at,
            admission.authority,
        )):
            return None
        if (
            isinstance(admission.property_lng, bool)
            or not isinstance(admission.property_lng, (int, float))
            or isinstance(admission.property_lat, bool)
            or not isinstance(admission.property_lat, (int, float))
        ):
            return None
        return admission

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def is_admitted_reality_record(
    value: object,
    *,
    property_id: str | None,
    property_identity: str | None,
    property_lng: float | None,
    property_lat: float | None,
) -> bool:
    """Validate the shared evidence/admission binding on a persisted record."""
    if (
        not isinstance(value, Mapping)
        or not property_id
        or not property_identity
        or property_lng is None
        or property_lat is None
    ):
        return False
    evidence = RealityEvidence.from_mapping(value.get("evidence"))
    admission = RealityAdmission.from_mapping(value.get("admission"))
    if evidence is None or admission is None or not evidence.qualifies():
        return False
    if (
        value.get("identity") != evidence.identity
        or (
            evidence.source_record_id is not None
            and value.get("external_id") != evidence.source_record_id
        )
    ):
        return False
    return admission.qualifies_for(
        property_id=property_id,
        property_identity=property_identity,
        property_lng=property_lng,
        property_lat=property_lat,
        evidence=evidence,
    )
