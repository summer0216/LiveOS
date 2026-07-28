import json

from app.core.ai_client import ai_client
from app.models.conversation import ConversationMessage
from app.models.profile_analysis import ProfileAnalysis
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

    def analyze(
        self,
        history: list[ConversationMessage],
    ) -> ProfileAnalysis:
        """
        根据 Conversation History,
        生成 ProfileAnalysis。
        """

        json_text = self.extract_json(history)

        return self._build_analysis(json_text)

    def _build_analysis(
        self,
        json_text: str,
    ) -> ProfileAnalysis:
        """
        将 LLM 返回的 JSON 字符串转换为
        ProfileAnalysis。
        """

        data = self._parse_json(json_text)

        patch = self._build_patch(data)
        insights = self._build_insights(data)

        return ProfileAnalysis(
            patch=patch,
            insights=insights,
        )

    def _parse_json(
        self,
        json_text: str,
    ) -> dict:
        """
        解析并验证 Profile Intelligence 返回的 JSON。
        """

        data = json.loads(json_text)

        if not isinstance(data, dict):
            raise ValueError(
                "Profile Intelligence response must be a JSON object.",
            )

        return data

    def _build_patch(
        self,
        data: dict,
    ) -> LivingProfilePatch:
        """
        将解析后的数据转换为 LivingProfilePatch。
        """

        return LivingProfilePatch(
            work_location=data.get("work_location"),
            budget=data.get("budget"),
            commute_minutes=data.get("commute_minutes"),
            preferred_city=data.get("preferred_city"),
            family_size=data.get("family_size"),
            has_pet=data.get("has_pet"),
        )

    def _build_insights(
        self,
        data: dict,
    ) -> list[str]:
        """
        根据已经识别出的 Profile 字段生成用户可见 Insights。
        """

        insight_labels = {
            "work_location": "已识别工作地点",
            "budget": "已识别预算",
            "commute_minutes": "已识别通勤要求",
            "preferred_city": "已识别意向城市",
            "family_size": "已识别家庭人数",
            "has_pet": "已识别宠物情况",
        }

        return [
            label
            for field, label in insight_labels.items()
            if data.get(field) is not None
        ]


profile_intelligence = ProfileIntelligence()
