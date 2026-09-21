from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Literal

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
from app.models.property import GeographicStatus, Property
from app.services.living_meaning_service import LivingMeaningService
from app.services.profile_manager import ProfileManager, profile_manager
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
        profiles: ProfileManager = profile_manager,
    ) -> None:
        self._properties = properties
        self._intelligence = intelligence
        self._evidence_search = evidence_search
        self._profiles = profiles

    def feedback_from_no_evidence(
        self, conversation_id: str, property_id: str,
    ) -> PublicRentActionResult:
        target = self._properties.get_scoped(property_id, conversation_id)
        if (
            target is None
            or target.public_action_outcome != "NO_EVIDENCE"
            or target.reality_action_type != "PUBLIC_EVIDENCE"
            or not target.reality_action_state_hash
            or not target.meaningful_unknown
            or not target.meaningful_unknown_why
            or not target.reality_action_label
            or target.rent is not None
            or target.public_rent_evidence is not None
            or not target.living_meaning
            or not target.current_judgment
        ):
            return PublicRentActionResult("NOT_AVAILABLE")
        profile = self._profiles.get(conversation_id)
        if profile is None or not LivingMeaningService._has_required_reality(
            target, profile
        ):
            return PublicRentActionResult("NOT_AVAILABLE")
        basis = LivingMeaningService._basis(target, profile)
        fingerprint = hashlib.sha256(json.dumps({
            "version": "v0.8-feedback",
            "unknown_hash": target.meaningful_unknown_state_hash,
            "unknown": target.meaningful_unknown,
            "action_hash": target.reality_action_state_hash,
            "action": target.reality_action_label,
            "outcome": target.public_action_outcome,
        }, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if (
            target.feedback_move_type
            and target.feedback_move_label
            and target.feedback_move_why
            and target.feedback_state_hash == fingerprint
        ):
            return PublicRentActionResult("NO_EVIDENCE", target)

        prompt = f"""
Re-judge how to advance one Possible Life after its public-evidence Reality
Action genuinely returned NO_EVIDENCE. This means this attempt obtained no
admissible evidence; it does NOT mean the evidence or Reality does not exist.
Choose ONE Next Move, not an answer and not a new Action execution.
Allowed types: USER_REALITY (user may directly know or observe the missing
Reality) or SHIFT_ATTENTION (keep this Unknown unresolved and move attention
to another uncertainty without generating it yet). Choose from this Decision
State; do not map NO_EVIDENCE or rent mechanically to one type.

Return JSON only with exactly:
{{"next_move_type":"USER_REALITY or SHIFT_ATTENTION",
  "next_move_label":"one concise Chinese next move",
  "why_this_move":"one concise Chinese explanation",
  "unknown_reference":"exact Unknown question",
  "action_reference":"exact Reality Action label",
  "outcome_reference":"NO_EVIDENCE"}}

Grounded Reality: {json.dumps(basis, ensure_ascii=False, sort_keys=True)}
Personal Meaning: {target.living_meaning}
Current Judgment: {target.current_judgment}
Unknown: {target.meaningful_unknown}
Why Unknown matters: {target.meaningful_unknown_why}
Reality Action: {target.reality_action_label}
Why Action: {target.reality_action_why}
Action Outcome: NO_EVIDENCE

Do not invent rent, claim no public evidence exists, resolve the Unknown,
recommend a Choice, or claim another Action was executed. Do not ask the user
through a Composer. Each Chinese field must be at most 65 characters.
""".strip()
        try:
            interpretation = json.loads(self._intelligence.generate_json(
                prompt,
                model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                max_output_tokens=320,
            ))
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return PublicRentActionResult("NO_EVIDENCE", target)
        if not isinstance(interpretation, dict) or set(interpretation) != {
            "next_move_type", "next_move_label", "why_this_move",
            "unknown_reference", "action_reference", "outcome_reference",
        }:
            return PublicRentActionResult("NO_EVIDENCE", target)
        move_type = interpretation.get("next_move_type")
        label = interpretation.get("next_move_label")
        why = interpretation.get("why_this_move")
        if (
            move_type not in {"USER_REALITY", "SHIFT_ATTENTION"}
            or interpretation.get("unknown_reference") != target.meaningful_unknown
            or interpretation.get("action_reference") != target.reality_action_label
            or interpretation.get("outcome_reference") != "NO_EVIDENCE"
            or not isinstance(label, str) or not label.strip()
            or len(label.strip()) > 65
            or not isinstance(why, str) or not why.strip()
            or len(why.strip()) > 65
        ):
            return PublicRentActionResult("NO_EVIDENCE", target)
        combined = f"{label} {why}"
        if any(term in combined for term in (
            "已确认", "已解决", "没有公开证据", "不存在公开证据",
            "已找到", "已查到", "租金是", "推荐", "最适合", "最佳",
        )):
            return PublicRentActionResult("NO_EVIDENCE", target)
        allowed_numbers = {
            number for value in basis.values() for number in re.findall(r"\d+", value)
        }
        if any(number not in allowed_numbers for number in re.findall(r"\d+", combined)):
            return PublicRentActionResult("NO_EVIDENCE", target)
        updated = self._properties.update_action_feedback(
            property_id, conversation_id,
            action_hash=target.reality_action_state_hash,
            move_type=move_type, label=label.strip(), why=why.strip(),
            state_hash=fingerprint,
        )
        return PublicRentActionResult(
            "NO_EVIDENCE" if updated else "NOT_AVAILABLE", updated,
        )

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
            return PublicRentActionResult("NOT_AVAILABLE")
        if not observed:
            recorded = self._properties.record_public_action_no_evidence(
                property_id, conversation_id,
                action_hash=target.reality_action_state_hash,
            )
            if recorded is None:
                return PublicRentActionResult("NOT_AVAILABLE")
            return self.feedback_from_no_evidence(conversation_id, property_id)
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
