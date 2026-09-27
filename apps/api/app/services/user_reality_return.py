"""Admit a focused user's answer to the active USER_REALITY Unknown."""

import json
from dataclasses import dataclass

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
from app.models.conversation import ConversationMessage
from app.models.property import GeographicStatus, Property, PropertyRentSource
from app.services.property_manager import PropertyManager, property_manager


def _amount_is_explicit(user_text: str, amount: int) -> bool:
    compact = user_text.replace(",", "")
    digits = str(amount)
    start = compact.find(digits)
    while start >= 0:
        end = start + len(digits)
        if (start == 0 or not compact[start - 1].isdigit()) and (
            end == len(compact) or not compact[end].isdigit()
        ):
            return True
        start = compact.find(digits, start + 1)
    return False


@dataclass(frozen=True)
class PropertyExpressionResolution:
    property_id: str | None = None
    reality_type: str | None = None
    needs_clarification: bool = False
    layout_requirement: str | None = None
    attention_property_id: str | None = None


class UserRealityReturn:
    def __init__(
        self, *, properties: PropertyManager = property_manager,
        intelligence: AIClient = ai_client,
    ) -> None:
        self._properties = properties
        self._intelligence = intelligence

    def resolve_expression(
        self, history: list[ConversationMessage], properties: list[Property],
        user_text: str, focused_property_id: str | None = None,
    ) -> PropertyExpressionResolution:
        """Understand claim nature and referent before Property admission."""
        candidates = [home for home in properties if (
            home.id and home.title and home.geographic_status == GeographicStatus.GROUNDED
        )]
        prior_user_texts = [
            item.content for item in history[:-1] if item.role == "user"
        ]
        prompt = f"""
Interpret the CURRENT user expression before any Property Reality admission.
Classify its nature as PERSONAL_REQUIREMENT, PROPERTY_REALITY, or OTHER.
An unqualified room count in a housing-search context may describe a desired
layout rather than an observed layout of a particular residence.
Do not turn a wish, constraint, requirement, or hypothetical into Property Reality.
PROPERTY_REALITY requires an explicit factual claim about an existing residence,
or a factual answer to its active Unknown. Resolve which residence it concerns
using the current expression, prior USER conversation, and Focus as context
evidence. Focus is not proof that every sentence describes that residence.
Prior user messages may establish an unambiguous referent. Mere candidate count
or map visibility never establishes one. Ignore assistant claims.

Prior user messages: {json.dumps(prior_user_texts, ensure_ascii=False)}
Current message: {json.dumps(user_text, ensure_ascii=False)}
Focused residence id (context evidence only): {json.dumps(focused_property_id)}
Grounded residences: {json.dumps([{"id": p.id, "title": p.title, "active_unknown": p.meaningful_unknown if p.meaningful_unknown_state_hash else None} for p in candidates], ensure_ascii=False)}

Return JSON only: {{"claim_nature": "PERSONAL_REQUIREMENT or PROPERTY_REALITY or OTHER",
"layout_requirement": "short exact current-user quote expressing their required room layout" or null,
"reality_type": "LAYOUT or RENT or TENANCY_MODE or INDEPENDENT_BATHROOM or INDEPENDENT_KITCHEN or INDOOR_SOUND_OBSERVATION" or null,
"claim_quote": "exact contiguous current-message quote" or null,
"property_id": "grounded residence id" or null,
"binding_evidence": "exact contiguous user quote naming the residence" or null,
"binding_source": "USER_EXPRESSION or FOCUS" or null,
"attention_property_id": "grounded residence id" or null,
"attention_evidence": "exact contiguous PRIOR user quote naming that residence" or null}}.
For PROPERTY_REALITY without reliable referent, return null property_id and
binding fields. For Focus binding, use FOCUS and null binding_evidence.
For requirement/other, return null reality_type, property_id, binding fields.
Attention is separate from Property Reality admission. Set attention_property_id
only when the CURRENT expression continues unambiguous attention to a residence
explicitly named by the USER in a PRIOR message. A requirement by itself, a
single visible/available residence, or Focus alone does not establish attention.
If the prior USER expression names one grounded home and the CURRENT expression
continues considering living there (including adding personal housing conditions),
return that home's attention id and the exact prior USER naming quote. Its
active_unknown may be null: an Unknown is not required to establish attention.
Keep a personal condition in layout_requirement, never in Property Reality.
Never set attention for an initial named-home grounding turn. If several homes
remain plausible, return null attention fields. Quote the prior user evidence;
do not use assistant text or a Property title from the candidate list alone.
Retain an explicit desired room layout in layout_requirement only when it is
the user's own requirement, including a terse requirement in a housing-search
context. Use an exact contiguous current-message quote, at most 60 characters.
Do not copy an actual residence layout into this field. A budget alone does not
establish a layout requirement. Return null when no layout requirement is stated.
""".strip()
        try:
            result = json.loads(self._intelligence.generate_json(
                prompt, model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                max_output_tokens=240,
            ))
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return PropertyExpressionResolution()
        if not isinstance(result, dict) or set(result) - {
            "layout_requirement", "attention_property_id", "attention_evidence",
        } != {
            "claim_nature", "reality_type", "claim_quote", "property_id",
            "binding_evidence", "binding_source",
        }:
            return PropertyExpressionResolution()
        attention_property_id = self._grounded_attention_target(
            result.get("attention_property_id"), result.get("attention_evidence"),
            prior_user_texts, user_text, candidates,
        )
        if result["claim_nature"] == "PERSONAL_REQUIREMENT":
            requirement = result.get("layout_requirement")
            if (
                isinstance(requirement, str) and requirement.strip()
                and len(requirement) <= 60 and requirement in user_text
                and result["property_id"] is None and result["reality_type"] is None
                and result["binding_source"] is None and result["binding_evidence"] is None
            ):
                return PropertyExpressionResolution(
                    layout_requirement=requirement,
                    attention_property_id=attention_property_id,
                )
            return PropertyExpressionResolution()
        if result["claim_nature"] != "PROPERTY_REALITY":
            return PropertyExpressionResolution()
        reality_type = result["reality_type"]
        if reality_type not in {
            "LAYOUT", "RENT", "TENANCY_MODE", "INDEPENDENT_BATHROOM",
            "INDEPENDENT_KITCHEN", "INDOOR_SOUND_OBSERVATION",
        }:
            return PropertyExpressionResolution()
        quote = result["claim_quote"]
        if not isinstance(quote, str) or not quote.strip() or quote not in user_text:
            return PropertyExpressionResolution()
        property_id = result["property_id"]
        evidence = result["binding_evidence"]
        if property_id is None:
            return PropertyExpressionResolution(needs_clarification=True)
        matches = [home for home in candidates if home.id == property_id]
        if len(matches) != 1:
            return PropertyExpressionResolution(needs_clarification=True)
        if result["binding_source"] == "FOCUS":
            if property_id != focused_property_id or evidence is not None:
                return PropertyExpressionResolution(needs_clarification=True)
        elif result["binding_source"] == "USER_EXPRESSION":
            user_texts = [*prior_user_texts, user_text]
            normalize = lambda value: "".join(char for char in value.casefold() if char.isalnum())
            if (not isinstance(evidence, str)
                    or not any(evidence in text for text in user_texts)
                    or normalize(matches[0].title) not in normalize(evidence)):
                return PropertyExpressionResolution(needs_clarification=True)
        else:
            return PropertyExpressionResolution(needs_clarification=True)
        return PropertyExpressionResolution(
            property_id, reality_type, attention_property_id=attention_property_id,
        )

    @staticmethod
    def _grounded_attention_target(
        property_id: object, evidence: object, prior_user_texts: list[str],
        user_text: str, candidates: list[Property],
    ) -> str | None:
        if not isinstance(property_id, str) or not isinstance(evidence, str):
            return None
        matches = [home for home in candidates if home.id == property_id]
        if len(matches) != 1 or not matches[0].title:
            return None
        normalize = lambda value: "".join(char for char in value.casefold() if char.isalnum())
        title = normalize(matches[0].title)
        if not title or title not in normalize(evidence):
            return None
        # Continuity must originate in a prior USER expression, not in the
        # current grounding turn or the existence of a lone Property row.
        anchor_indices = [
            index for index, message in enumerate(prior_user_texts)
            if evidence in message
        ]
        if not anchor_indices:
            return None
        anchor_index = max(anchor_indices)
        for message in [*prior_user_texts[anchor_index:], user_text]:
            named = {
                home.id for home in candidates
                if home.title and normalize(home.title) in normalize(message)
            }
            if named and named != {property_id}:
                return None
        return property_id

    def admit(
        self, conversation_id: str, property_id: str, user_text: str,
        *, expected_reality_type: str | None = None,
    ) -> Property | None:
        home = self._properties.get_scoped(property_id, conversation_id)
        if home is None or home.geographic_status != GeographicStatus.GROUNDED:
            return None

        active_unknown = bool(
            home.meaningful_unknown
            and home.meaningful_unknown_state_hash
        )

        prompt = f"""
Determine whether the CURRENT user message explicitly states supported Reality
for this one focused residence. It may answer the active Decision-Relevant
Unknown or proactively state factual rent or a concrete residential layout.
Do not use prior assistant claims
as evidence. Focus may resolve which residence "this one" refers to, but an
unrelated or ambiguous message must not become Reality.

Focused residence: {json.dumps(home.title, ensure_ascii=False)}
Active Unknown: {json.dumps(home.meaningful_unknown if active_unknown else None, ensure_ascii=False)}
Current user message: {json.dumps(user_text, ensure_ascii=False)}

Supported Reality slots in this focused Possible Life:
- LAYOUT: a factual description of this focused residence's room layout.
  Value must be the shortest exact contiguous quote from this user message
  that states the layout. Do not convert a desired, hypothetical, or
  comparative layout into a fact. Do not infer a price or suitability.
- INDEPENDENT_BATHROOM: an explicit factual yes/no answer about whether the
  rented room/residence has a bathroom for its exclusive use. Value must be
  a JSON boolean. Interpret short answers against the active Unknown only.
  Do not infer bathroom count, privacy, cleanliness, quality, suitability,
  preference or value. Ambiguous, hypothetical or desired arrangements are NONE.
- TENANCY_MODE: an explicit factual answer to the active tenancy Unknown.
  Value is ENTIRE_RENT or SHARED_RENT. Interpret a short answer in the
  active question's context; wishes, hypotheticals and ambiguity are NONE.
  This establishes tenancy arrangement only, not privacy, quality or fit.
- RENT: an explicit factual monthly rent amount for this focused residence,
  even if no Unknown or Action asked for it. Value must be a JSON integer.
  A wish, budget, target, hypothetical, quote about another residence, or
  ambiguous amount is NOT rent Reality.
- INDEPENDENT_KITCHEN: a clear user-provided yes/no fact about a usable
  independent kitchen. Value must be a JSON boolean.
- INDOOR_SOUND_OBSERVATION: a direct user observation materially informing
  the active indoor-sound Unknown. Value must be an exact, contiguous quote
  from the current user message, preserving time and conditions. It describes
  only what the user observed, not a universal noise level or measurement.

Select RENT only for a factual rent statement about the focused residence.
Select LAYOUT for a factual user statement about this focused residence even
without an active Unknown. Select the other slots only when they actually
answer the active Unknown.
Return JSON only with exactly these fields:
{{"unknown_reference": "exact active Unknown", "reality_type":
  "RENT or LAYOUT or TENANCY_MODE or INDEPENDENT_BATHROOM or INDEPENDENT_KITCHEN or INDOOR_SOUND_OBSERVATION or NONE",
  "value": "integer, exact user quote, boolean, or null"}}
For RENT, LAYOUT, or when there is no active Unknown, unknown_reference must be null.
Use reality_type=NONE and value=null if unrelated, hypothetical, ambiguous,
or not a supported Reality. Never turn a preference into observed rent.
Never guess, summarize an observation into a rating, invent dB, or use
assistant inference.
""".strip()
        try:
            result = json.loads(self._intelligence.generate_json(
                prompt,
                model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                max_output_tokens=240,
            ))
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return None
        if (
            not isinstance(result, dict)
            or set(result) != {"unknown_reference", "reality_type", "value"}
        ):
            return None
        if expected_reality_type is not None and result["reality_type"] != expected_reality_type:
            return None
        if result["reality_type"] == "RENT":
            rent = result["value"]
            if (
                result["unknown_reference"] is not None
                or type(rent) is not int
                or not 1 <= rent <= 99_999_999
                or not _amount_is_explicit(user_text, rent)
            ):
                return None
            if home.rent == rent and home.rent_source == PropertyRentSource.USER_PROVIDED:
                return home
            return self._properties.update_confirmed_rent(
                property_id, conversation_id, rent, PropertyRentSource.USER_PROVIDED,
            )
        if result["reality_type"] == "LAYOUT":
            quote = result["value"]
            if (
                result["unknown_reference"] is not None
                or not isinstance(quote, str)
                or not quote.strip()
                or len(quote) > 60
                or quote not in user_text
            ):
                return None
            if home.layout_expression == quote and home.layout_source == "USER_PROVIDED":
                return home
            return self._properties.admit_user_layout_reality(
                property_id, conversation_id, expression=quote,
            )
        if not active_unknown or result["unknown_reference"] != home.meaningful_unknown:
            return None
        if result["reality_type"] == "TENANCY_MODE":
            if home.tenancy_mode is not None or result["value"] not in (
                "ENTIRE_RENT", "SHARED_RENT",
            ):
                return None
            return self._properties.admit_user_tenancy_reality(
                property_id, conversation_id,
                unknown_hash=home.meaningful_unknown_state_hash,
                tenancy_mode=result["value"],
            )
        if result["reality_type"] == "INDEPENDENT_BATHROOM":
            if home.independent_bathroom is not None or type(result["value"]) is not bool:
                return None
            return self._properties.admit_user_bathroom_reality(
                property_id, conversation_id,
                unknown_hash=home.meaningful_unknown_state_hash,
                independent_bathroom=result["value"],
            )
        if result["reality_type"] == "INDEPENDENT_KITCHEN":
            if home.independent_kitchen is not None or type(result["value"]) is not bool:
                return None
            return self._properties.admit_user_kitchen_reality(
                property_id, conversation_id,
                unknown_hash=home.meaningful_unknown_state_hash,
                kitchen_present=result["value"],
            )
        if result["reality_type"] == "INDOOR_SOUND_OBSERVATION":
            quote = result["value"]
            if (
                home.indoor_sound_observation is not None
                or not isinstance(quote, str)
                or not quote.strip()
                or len(quote) > 300
                or quote not in user_text
            ):
                return None
            return self._properties.admit_user_sound_observation(
                property_id, conversation_id,
                unknown_hash=home.meaningful_unknown_state_hash,
                unknown_question=home.meaningful_unknown,
                observation=quote.strip(),
            )
        return None


user_reality_return = UserRealityReturn()
