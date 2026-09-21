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
            or home.independent_kitchen is not None
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

This bounded Reality slot records whether this residence has an independent
kitchen usable for daily life. Admit only a clear user-provided yes/no answer
to that exact Unknown. If the Unknown is about something else, return null.
Return JSON only with exactly:
{{"unknown_reference": "exact active Unknown", "answers_unknown": true,
  "independent_kitchen": true}}
For no clear answer use answers_unknown=false and independent_kitchen=null.
Never guess, infer an amenity from a neighborhood, or use assistant inference.
""".strip()
        try:
            result = json.loads(self._intelligence.generate_json(
                prompt,
                model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                max_output_tokens=160,
            ))
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return None
        if (
            not isinstance(result, dict)
            or set(result) != {
                "unknown_reference", "answers_unknown", "independent_kitchen"
            }
            or result["unknown_reference"] != home.meaningful_unknown
            or result["answers_unknown"] is not True
            or type(result["independent_kitchen"]) is not bool
        ):
            return None
        return self._properties.admit_user_kitchen_reality(
            property_id, conversation_id,
            unknown_hash=home.meaningful_unknown_state_hash,
            kitchen_present=result["independent_kitchen"],
        )


user_reality_return = UserRealityReturn()
