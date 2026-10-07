from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from typing import Literal
from uuid import uuid4

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
from app.core.external_rent_observability import record_external_rent_search_trace
from app.models.property import GeographicStatus, Property
from app.models.reality_evidence import RealityAdmission
from app.services.living_meaning_service import (
    LivingMeaningService,
    living_meaning_service,
)
from app.services.profile_manager import ProfileManager, profile_manager
from app.services.property_manager import PropertyManager, property_manager
from app.services.public_rental_evidence import (
    PublicRentalEvidence,
    PublicRentalEvidenceSearch,
    public_rental_evidence_search,
)

ExternalRentStatus = Literal["UPDATED", "NO_RELIABLE_EVIDENCE", "NOT_FOUND"]
logger = logging.getLogger(__name__)
USER_INITIATED_RENT_ACTION_LABEL = "查询这处住所的公开租金信息"
USER_INITIATED_RENT_ACTION_WHY = "用户明确请求核实这处住所的实际租金"


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
        meanings: LivingMeaningService = living_meaning_service,
    ) -> None:
        self._properties = properties
        self._intelligence = intelligence
        self._evidence_search = evidence_search
        self._profiles = profiles
        self._meanings = meanings

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
        user_initiated = self._is_user_initiated_rent_action(target)
        if (
            target is None
            or target.reality_action_type != "PUBLIC_EVIDENCE"
            or not target.reality_action_state_hash
            or (not target.meaningful_unknown and not user_initiated)
            or target.rent is not None
            or not target.title
            or target.geographic_status != GeographicStatus.GROUNDED
            or target.lng is None
            or target.lat is None
        ):
            return PublicRentActionResult("NOT_AVAILABLE")
        if target.public_rent_evidence is not None:
            return PublicRentActionResult("EVIDENCE_READY", target)

        execution_id = uuid4().hex
        record_external_rent_search_trace(
            execution_id, "public_action_execution_started",
            property_id=property_id,
        )
        orchestration_stage = "not_started"

        def record_orchestration_stage(stage: str) -> None:
            nonlocal orchestration_stage
            orchestration_stage = stage
            record_external_rent_search_trace(
                execution_id, "orchestration_stage", stage=stage,
            )

        def record_tool_arguments(arguments: str) -> None:
            record_external_rent_search_trace(
                execution_id, "tool_arguments", arguments=arguments,
            )

        observed: list[PublicRentalEvidence] = []

        def dispatch(_arguments: dict) -> str:
            record_external_rent_search_trace(
                execution_id, "search_tool_dispatched", tool="search_public_rental_evidence",
            )
            found = self._evidence_search.search(
                property_name=target.title or "",
                property_identity=target.geographic_identity or "",
                city=target.district,
                district=target.geographic_identity,
                lng=target.lng,
                lat=target.lat,
                trace_id=execution_id,
            )
            observed.extend(found)
            record_external_rent_search_trace(
                execution_id, "search_tool_returned", evidence_count=len(found),
            )
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
                on_stage=record_orchestration_stage,
                on_tool_arguments=record_tool_arguments,
            )
        except (RuntimeError, TypeError, ValueError) as exc:
            record_external_rent_search_trace(
                execution_id, "public_action_execution_failed",
                stage=orchestration_stage,
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                call_context={
                    "method": "generate_json_with_public_evidence_tool",
                    "tool": "search_public_rental_evidence",
                    "property_id": property_id,
                },
            )
            return PublicRentActionResult("NOT_AVAILABLE")
        grounded = self._ground_public_evidence(observed, target)
        if not grounded:
            record_external_rent_search_trace(
                execution_id, "public_action_execution_complete",
                outcome="NO_EVIDENCE", evidence_count=0,
            )
            recorded = self._properties.record_public_action_no_evidence(
                property_id, conversation_id,
                action_hash=target.reality_action_state_hash,
            )
            if recorded is None:
                return PublicRentActionResult("NOT_AVAILABLE")
            if user_initiated:
                return PublicRentActionResult("NO_EVIDENCE", recorded)
            return self.feedback_from_no_evidence(conversation_id, property_id)
        updated = self._properties.update_public_rent_evidence(
            property_id, conversation_id,
            action_hash=target.reality_action_state_hash,
            evidence=asdict(grounded[0]),
        )
        if updated is not None:
            understanding = self._understand_grounded_public_evidence(grounded[0])
            if understanding is not None:
                updated = self._properties.update_public_rent_understanding(
                    property_id,
                    conversation_id,
                    action_hash=target.reality_action_state_hash,
                    source_reference=grounded[0].source_reference,
                    understanding=understanding,
                )
                if updated is not None:
                    try:
                        consequence = self._meanings.form(conversation_id, property_id)
                        if consequence.property is not None:
                            updated = consequence.property
                    except Exception:
                        logger.exception(
                            "Failed to refresh Living Meaning after public evidence understanding"
                        )
        record_external_rent_search_trace(
            execution_id, "public_action_execution_complete",
            outcome="EVIDENCE_READY" if updated else "NOT_AVAILABLE",
            evidence_count=len(observed),
        )
        return PublicRentActionResult(
            "EVIDENCE_READY" if updated else "NOT_AVAILABLE", updated,
        )

    @staticmethod
    def _is_user_initiated_rent_action(target: Property | None) -> bool:
        return bool(
            target is not None
            and target.reality_action_type == "PUBLIC_EVIDENCE"
            and target.meaningful_unknown is None
            and target.reality_action_label == USER_INITIATED_RENT_ACTION_LABEL
            and target.reality_action_why == USER_INITIATED_RENT_ACTION_WHY
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
                property_identity=target.geographic_identity or "",
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
states one current monthly rent. evidence_excerpt must be a short exact
contiguous passage from that source containing the property's full grounded
geographic identity and its monthly rent. If the source cannot identify the
same place, return UNRESOLVED. Never estimate, average, or infer a missing amount.
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

        admitted = self._admit(interpretation, observed, target)
        if admitted is None:
            return ExternalRentResult("NO_RELIABLE_EVIDENCE")
        rent, source, excerpt = admitted
        reality_admission = RealityAdmission.admit(
            source.reality_evidence(),
            property_id=target.id or "",
            property_identity=target.geographic_identity or "",
            property_lng=target.lng,
            property_lat=target.lat,
            authority="EXTERNAL_RENT_REALITY_ADMISSION",
        )
        if reality_admission is None:
            return ExternalRentResult("NO_RELIABLE_EVIDENCE")
        updated = self._properties.update_external_rent(
            property_id,
            conversation_id,
            rent,
            source_reference=source.source_reference,
            observed_at=source.observed_at,
            evidence={
                **asdict(source),
                "admission": {
                    **reality_admission.to_dict(),
                    "property_id": target.id,
                    "property_identity": target.geographic_identity,
                    "rent_monthly": rent,
                    "evidence_excerpt": excerpt,
                },
            },
        )
        if updated is not None:
            try:
                consequence = self._meanings.form(conversation_id, property_id)
                if consequence.property is not None:
                    updated = consequence.property
            except Exception:
                logger.exception(
                    "Failed to refresh Living Meaning after external rent admission"
                )
        return ExternalRentResult(
            "UPDATED" if updated else "NOT_FOUND",
            property=updated,
        )

    @staticmethod
    def _ground_public_evidence(
        evidence: list[PublicRentalEvidence], target: Property,
    ) -> list[PublicRentalEvidence]:
        if not target.geographic_identity:
            return []
        grounded: list[PublicRentalEvidence] = []
        for item in evidence:
            if not item.reality_evidence().qualifies(
                expected_identity=target.geographic_identity,
            ):
                continue
            grounded.append(item)
        return grounded

    def _understand_grounded_public_evidence(
        self, evidence: PublicRentalEvidence,
    ) -> dict[str, object] | None:
        prompt = f"""
Interpret ONE admitted, identity-grounded public rental Evidence item.
The Evidence proves only one observed rental possibility from one source at
one observation time. It does not establish this Property's actual rent,
market rent, average, typical value, or a rent range.

Return JSON only with exactly:
{{"claim_type":"SINGLE_OBSERVATION or INSUFFICIENT",
  "rent_monthly":integer or null,
  "source_reference":string or null,
  "observed_at":string or null,
  "evidence_excerpt":"short exact contiguous source passage" or null}}

Grounded Evidence:
{json.dumps(asdict(evidence), ensure_ascii=False, sort_keys=True)}

Use SINGLE_OBSERVATION only when one exact monthly rent is explicitly present.
Copy its source_reference and observed_at exactly. The excerpt must be a short
contiguous passage from property_text containing exactly one monthly rent.
Otherwise return INSUFFICIENT with all other fields null. Do not estimate,
average, derive a range, generalize to the Property, or invent provenance.
""".strip()
        try:
            interpretation = json.loads(self._intelligence.generate_json(
                prompt,
                model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                max_output_tokens=256,
            ))
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return None
        return self._validate_rent_understanding(interpretation, evidence)

    @staticmethod
    def _validate_rent_understanding(
        interpretation: object, evidence: PublicRentalEvidence,
    ) -> dict[str, object] | None:
        if not isinstance(interpretation, dict) or set(interpretation) != {
            "claim_type", "rent_monthly", "source_reference", "observed_at",
            "evidence_excerpt",
        }:
            return None
        if interpretation.get("claim_type") != "SINGLE_OBSERVATION":
            return None
        amount = interpretation.get("rent_monthly")
        excerpt = interpretation.get("evidence_excerpt")
        if (
            not isinstance(amount, int)
            or isinstance(amount, bool)
            or amount <= 0
            or interpretation.get("source_reference") != evidence.source_reference
            or interpretation.get("observed_at") != evidence.observed_at
            or not isinstance(excerpt, str)
            or not 1 <= len(excerpt) <= 300
            or excerpt not in evidence.property_text
        ):
            return None
        compact_excerpt = excerpt.replace(",", "").replace("，", "")
        amounts = re.findall(
            r"(?<!\d)(\d{1,8})\s*(?:元\s*/\s*月|元\s*每月|元\s*月租|元\s*一个月|元\s*每个月)",
            compact_excerpt,
        )
        if len(amounts) != 1 or int(amounts[0]) != amount:
            return None
        return {
            "claim_type": "SINGLE_OBSERVATION",
            "rent_monthly": amount,
            "understanding": f"当前发现一种约 ¥{amount:,}/月的真实租赁可能。",
            "source_reference": evidence.source_reference,
            "observed_at": evidence.observed_at,
            "evidence_excerpt": excerpt,
        }

    @staticmethod
    def _admit(
        interpretation: object,
        evidence: list[PublicRentalEvidence],
        target: Property,
    ) -> tuple[int, PublicRentalEvidence, str] | None:
        if not isinstance(interpretation, dict):
            return None
        rent = interpretation.get("rent_monthly")
        source_reference = interpretation.get("source_reference")
        observed_at = interpretation.get("observed_at")
        excerpt = interpretation.get("evidence_excerpt")
        if (
            interpretation.get("identity_status") != "GROUNDED"
            or not isinstance(rent, int)
            or isinstance(rent, bool)
            or rent <= 0
            or not isinstance(source_reference, str)
            or not isinstance(observed_at, str)
            or not isinstance(excerpt, str)
            or not 1 <= len(excerpt) <= 300
            or not target.title
            or not target.geographic_identity
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
        if (
            source is None
            or not source.reality_evidence().qualifies(
                expected_identity=target.geographic_identity,
            )
        ):
            return None
        normalized_identity = re.sub(
            r"[\s·・•()（）-]", "", target.geographic_identity,
        ).casefold()
        normalized_excerpt = re.sub(r"[\s·・•()（）-]", "", excerpt).casefold()
        if (
            excerpt not in source.property_text
            or not normalized_identity
            or normalized_identity not in normalized_excerpt
        ):
            return None
        compact_excerpt = excerpt.replace(",", "").replace("，", "")
        amounts = re.findall(r"(?<!\d)(\d{1,8})\s*(?:元\s*/\s*月|元\s*每月|元\s*月租|元\s*一个月|元\s*每个月)", compact_excerpt)
        if len(amounts) != 1 or int(amounts[0]) != rent:
            return None
        return rent, source, excerpt


external_rent_reality_service = ExternalRentRealityService()
