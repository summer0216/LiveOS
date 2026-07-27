import json

from app.core.ai_client import ai_client
from app.models.conversation import ConversationMessage
from app.models.profile_patch import LivingProfilePatch
from app.runtime.prompt import build_profile_extraction_prompt


class ProfileIntelligence:
    def extract_json(
        self,
        history: list[ConversationMessage],
    ) -> str:
        """
        根据 Conversation History 调用 LLM,
        返回原始 Profile JSON 字符串。
        """

        prompt = build_profile_extraction_prompt(history)

        return ai_client.generate_json(prompt)

    def extract(
        self,
        history: list[ConversationMessage],
    ) -> LivingProfilePatch:
        """
        根据 Conversation History,
        生成结构化 LivingProfilePatch。
        """

        json_text = self.extract_json(history)

        return self._build_patch(json_text)

    def _build_patch(
        self,
        json_text: str,
    ) -> LivingProfilePatch:
        """
        将 LLM 返回的 JSON 字符串转换为
        LivingProfilePatch。
        """

        data = json.loads(json_text)

        if not isinstance(data, dict):
            raise ValueError(
                "Profile Intelligence response must be a JSON object.",
            )

        return LivingProfilePatch(
            work_location=data.get("work_location"),
            budget=data.get("budget"),
            commute_minutes=data.get("commute_minutes"),
            preferred_city=data.get("preferred_city"),
            family_size=data.get("family_size"),
            has_pet=data.get("has_pet"),
        )


profile_intelligence = ProfileIntelligence()
