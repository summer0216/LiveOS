"""Admit an explicit user decision about one focused ready Possible Life."""

import json

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
from app.models.property import GeographicStatus, Property
from app.services.property_manager import PropertyManager, property_manager


class UserDecisionReturn:
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
            or home.decision_readiness != "DECISION_READY"
            or not home.decision_readiness_state_hash
            or home.user_decision_expression is not None
            or not user_text.strip()
            or len(user_text) > 500
        ):
            return None

        prompt = f"""
Interpret ONLY the current user's expression about the one focused, decision-ready
Possible Life. Current Judgment is LiveOS's provisional interpretation, NOT
the user's decision. A user decision must be explicitly expressed by the user.
Do not use assistant text or previous conversation as evidence of a decision.

Focused residence: {json.dumps(home.title, ensure_ascii=False)}
Current Judgment (context only): {json.dumps(home.current_judgment, ensure_ascii=False)}
Current user expression: {json.dumps(user_text, ensure_ascii=False)}

Classify the user's own stance toward living in this focused residence:
ACCEPT = explicitly willing to accept/choose this trade-off;
DECLINE = explicitly rejecting this residence/trade-off;
NONE = question, observation, hypothetical, ambiguous, or no explicit decision.
Do not infer a choice from facts, tone, or the Current Judgment. If the user
clearly refers to another residence, return NONE. Return JSON only with
exactly {{"stance":"ACCEPT|DECLINE|NONE", "user_expression":"exact current user expression"}}.
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
            or set(result) != {"stance", "user_expression"}
            or result["stance"] not in {"ACCEPT", "DECLINE"}
            or result["user_expression"] != user_text
        ):
            return None
        return self._properties.admit_user_decision(
            property_id, conversation_id,
            readiness_hash=home.decision_readiness_state_hash,
            expression=user_text, stance=result["stance"],
        )


user_decision_return = UserDecisionReturn()
