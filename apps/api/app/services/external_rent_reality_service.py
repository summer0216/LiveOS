from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Literal

from app.core.ai_client import AIClient, ai_client
from app.models.property import GeographicStatus, Property
from app.services.property_manager import PropertyManager, property_manager
from app.services.public_rental_evidence import (
    PublicRentalEvidence,
    PublicRentalEvidenceSearch,
    public_rental_evidence_search,
)

ExternalRentStatus = Literal["UPDATED", "NO_RELIABLE_EVIDENCE", "NOT_FOUND"]


@dataclass(frozen=True)
class ExternalRentResult:
    status: ExternalRentStatus
    property: Property | None = None


@dataclass(frozen=True)
class PublicRentActionResult:
    status: Literal["EVIDENCE_READY", "NO_EVIDENCE", "NOT_AVAILABLE"]
    property: Property | None = None


PUBLIC_RENT_TOOL = {
    "type": "function",
    "function": {
        "name": "search_public_rental_evidence",
        "description": "Search traceable current public rental evidence for the grounded Possible Life.",
        "parameters": {
            "type": "object",
            "properties": {
                "property_name": {"type": "string"},
                "city": {"type": "string"},
                "district": {"type": "string"},
                "lng": {"type": "number"},
                "lat": {"type": "number"},
            },
            "required": ["property_name"],
            "additionalProperties": False,
        },
    },
}


class ExternalRentRealityService:
    def __init__(
        self,
        *,
        properties: PropertyManager = property_manager,
        intelligence: AIClient = ai_client,
        evidence_search: PublicRentalEvidenceSearch = public_rental_evidence_search,
    ) -> None:
        self._properties = properties
        self._intelligence = intelligence
        self._evidence_search = evidence_search

    def execute_public_evidence_action(
        self, conversation_id: str, property_id: str,
    ) -> PublicRentActionResult:
        target = self._properties.get_scoped(property_id, conversation_id)
        if (
            target is None
            or target.reality_action_type != "PUBLIC_EVIDENCE"
            or not target.reality_action_state_hash
            or not target.meaningful_unknown
            or target.rent is not None
            or not target.title
            or target.geographic_status != GeographicStatus.GROUNDED
            or target.lng is None
            or target.lat is None
        ):
            return PublicRentActionResult("NOT_AVAILABLE")
        if target.public_rent_evidence is not None:
            return PublicRentActionResult("EVIDENCE_READY", target)

        observed: list[PublicRentalEvidence] = []

        def dispatch(_arguments: dict) -> str:
            observed.extend(self._evidence_search.search(
                property_name=target.title or "",
                city=target.district,
                district=target.geographic_identity,
                lng=target.lng,
                lat=target.lat,
            ))
            return self._evidence_search.as_tool_result(observed)

        prompt = f"""
Execute the user's PUBLIC_EVIDENCE Reality Action for one grounded Possible Life.
Property: {target.title}
Geographic identity: {target.geographic_identity}
Coordinates: {target.lng},{target.lat}
Unresolved question: {target.meaningful_unknown}
Call search_public_rental_evidence exactly once. Return JSON {{"done": true}}.
Do not admit evidence as Rent Reality or answer the unresolved question.
""".strip()
        try:
            self._intelligence.generate_json_with_public_evidence_tool(
                prompt, tool=PUBLIC_RENT_TOOL, dispatch=dispatch,
            )
        except (RuntimeError, TypeError, ValueError):
            return PublicRentActionResult("NO_EVIDENCE")
        if not observed:
            return PublicRentActionResult("NO_EVIDENCE")
        updated = self._properties.update_public_rent_evidence(
            property_id, conversation_id,
            action_hash=target.reality_action_state_hash,
            evidence=asdict(observed[0]),
        )
        return PublicRentActionResult(
            "EVIDENCE_READY" if updated else "NOT_AVAILABLE", updated,
        )

    def acquire(self, conversation_id: str, property_id: str) -> ExternalRentResult:
        target = self._properties.get_scoped(property_id, conversation_id)
        if (
            target is None
            or not target.title
            or target.geographic_status != GeographicStatus.GROUNDED
            or target.lng is None
            or target.lat is None
        ):
            return ExternalRentResult("NOT_FOUND")

        observed: list[PublicRentalEvidence] = []

        def dispatch(_arguments: dict) -> str:
            # Model arguments express its tool decision; authoritative stored Reality
            # supplies the actual search boundary.
            observed.extend(self._evidence_search.search(
                property_name=target.title or "",
                city=target.district,
                district=target.geographic_identity,
                lng=target.lng,
                lat=target.lat,
            ))
            return self._evidence_search.as_tool_result(observed)

        prompt = f"""
You are resolving one missing Rent Reality for an existing grounded Possible Life.
The current property is authoritative application state:
- property_name: {target.title}
- city_or_district: {target.district}
- geographic_identity: {target.geographic_identity}
- coordinates: {target.lng},{target.lat}

Call search_public_rental_evidence exactly once. Then interpret only returned evidence.
Return JSON only:
{{
  "rent_monthly": integer | null,
  "identity_status": "GROUNDED" | "UNRESOLVED",
  "source_reference": string | null,
  "observed_at": string | null,
  "evidence_excerpt": string | null
}}
Use GROUNDED only when one fetched source clearly refers to this property and explicitly
states one current monthly rent. Never estimate, average, or infer a missing amount.
""".strip()
        try:
            raw = self._intelligence.generate_json_with_public_evidence_tool(
                prompt,
                tool=PUBLIC_RENT_TOOL,
                dispatch=dispatch,
            )
            interpretation = json.loads(raw)
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return ExternalRentResult("NO_RELIABLE_EVIDENCE")

        admitted = self._admit(interpretation, observed)
        if admitted is None:
            return ExternalRentResult("NO_RELIABLE_EVIDENCE")
        rent, source_reference, observed_at = admitted
        updated = self._properties.update_external_rent(
            property_id,
            conversation_id,
            rent,
            source_reference=source_reference,
            observed_at=observed_at,
        )
        return ExternalRentResult(
            "UPDATED" if updated else "NOT_FOUND",
            property=updated,
        )

    @staticmethod
    def _admit(
        interpretation: object,
        evidence: list[PublicRentalEvidence],
    ) -> tuple[int, str, str] | None:
        if not isinstance(interpretation, dict):
            return None
        rent = interpretation.get("rent_monthly")
        source_reference = interpretation.get("source_reference")
        observed_at = interpretation.get("observed_at")
        if (
            interpretation.get("identity_status") != "GROUNDED"
            or not isinstance(rent, int)
            or isinstance(rent, bool)
            or rent <= 0
            or not isinstance(source_reference, str)
            or not isinstance(observed_at, str)
        ):
            return None
        source = next(
            (
                item for item in evidence
                if item.source_reference == source_reference
                and item.observed_at == observed_at
            ),
            None,
        )
        if source is None:
            return None
        compact_text = source.property_text.replace(",", "")
        if re.search(rf"(?<!\d){rent}(?!\d)", compact_text) is None:
            return None
        return rent, source_reference, observed_at


external_rent_reality_service = ExternalRentRealityService()
