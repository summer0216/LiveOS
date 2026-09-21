"""Admit a focused user's answer to the active USER_REALITY Unknown."""

import json

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
from app.models.property import GeographicStatus, Property
from app.services.property_manager import PropertyManager, property_manager


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
        if (
            home is None
            or home.geographic_status != GeographicStatus.GROUNDED
            or not home.meaningful_unknown
            or not home.meaningful_unknown_state_hash
            or (home.reality_action_type != "USER_REALITY"
                and home.feedback_move_type != "USER_REALITY")
        ):
            return None

        prompt = f"""
Determine whether the CURRENT user message explicitly answers the active
Decision-Relevant Unknown for this one focused residence. Do not use prior
assistant claims as evidence. Context can resolve what "I asked" refers to,
but an unrelated or ambiguous message must not become Reality.

Focused residence: {json.dumps(home.title, ensure_ascii=False)}
Active Unknown: {json.dumps(home.meaningful_unknown, ensure_ascii=False)}
Current user message: {json.dumps(user_text, ensure_ascii=False)}

Supported Reality slots in this focused Possible Life:
- INDEPENDENT_KITCHEN: a clear user-provided yes/no fact about a usable
  independent kitchen. Value must be a JSON boolean.
- INDOOR_SOUND_OBSERVATION: a direct user observation materially informing
  the active indoor-sound Unknown. Value must be an exact, contiguous quote
  from the current user message, preserving time and conditions. It describes
  only what the user observed, not a universal noise level or measurement.

Select only the slot actually answered by the current message and active
Unknown. Return JSON only with exactly these fields:
{{"unknown_reference": "exact active Unknown", "reality_type":
  "INDEPENDENT_KITCHEN or INDOOR_SOUND_OBSERVATION or NONE",
  "value": "exact user quote, boolean, or null"}}
Use reality_type=NONE and value=null if unrelated, hypothetical, ambiguous,
or not a supported Reality. Never guess, summarize an observation into a
rating, invent dB, or use assistant inference.
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
            or result["unknown_reference"] != home.meaningful_unknown
        ):
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
