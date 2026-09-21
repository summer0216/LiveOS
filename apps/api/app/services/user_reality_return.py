"""Admit a focused user's answer to the active USER_REALITY Unknown."""

import json

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
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


class UserRealityReturn:
    def __init__(
        self, *, properties: PropertyManager = property_manager,
        intelligence: AIClient = ai_client,
    ) -> None:
        self._properties = properties
        self._intelligence = intelligence

    def admit(
        self, conversation_id: str, property_id: str, user_text: str,
    ) -> Property | None:
        home = self._properties.get_scoped(property_id, conversation_id)
        if home is None or home.geographic_status != GeographicStatus.GROUNDED:
            return None

        active_unknown = bool(
            home.meaningful_unknown
            and home.meaningful_unknown_state_hash
            and (home.reality_action_type == "USER_REALITY"
                 or home.feedback_move_type == "USER_REALITY")
        )

        prompt = f"""
Determine whether the CURRENT user message explicitly states supported Reality
for this one focused residence. It may answer the active Decision-Relevant
Unknown or proactively state factual rent. Do not use prior assistant claims
as evidence. Focus may resolve which residence "this one" refers to, but an
unrelated or ambiguous message must not become Reality.

Focused residence: {json.dumps(home.title, ensure_ascii=False)}
Active Unknown: {json.dumps(home.meaningful_unknown if active_unknown else None, ensure_ascii=False)}
Current user message: {json.dumps(user_text, ensure_ascii=False)}

Supported Reality slots in this focused Possible Life:
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
Select the other slots only when they actually answer the active Unknown.
Return JSON only with exactly these fields:
{{"unknown_reference": "exact active Unknown", "reality_type":
  "RENT or INDEPENDENT_KITCHEN or INDOOR_SOUND_OBSERVATION or NONE",
  "value": "integer, exact user quote, boolean, or null"}}
For RENT or when there is no active Unknown, unknown_reference must be null.
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
        if not active_unknown or result["unknown_reference"] != home.meaningful_unknown:
            return None
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
