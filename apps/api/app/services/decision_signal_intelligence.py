import json

from app.core.ai_client import ai_client
from app.core.config import settings
from app.models.decision_geography import DecisionGeography
from app.runtime.prompt import build_decision_signal_prompt
from app.services.profile_intelligence import profile_intelligence


class DecisionSignalIntelligence:
    def analyze(self, user_message: str) -> DecisionGeography:
        payload = json.loads(
            ai_client.generate_json(
                build_decision_signal_prompt(user_message),
                model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                max_output_tokens=256,
            )
        )
        return profile_intelligence._build_decision_geography(payload, user_message)


decision_signal_intelligence = DecisionSignalIntelligence()
