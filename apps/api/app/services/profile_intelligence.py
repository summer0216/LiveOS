import json
import re
from dataclasses import replace

from app.core.ai_client import ai_client
from app.models.conversation import ConversationMessage
from app.models.decision_feedback import (
    NO_DECISION_FEEDBACK,
    DecisionRelevantFeedback,
)
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

        latest_user_message = next(
            (
                message.content
                for message in reversed(history)
                if message.role == "user"
            ),
            "",
        )
        return self._build_analysis(json_text, latest_user_message)

    def _build_analysis(
        self,
        json_text: str,
        latest_user_message: str = "",
    ) -> ProfileAnalysis:
        """
        将 LLM 返回的 JSON 字符串转换为
        ProfileAnalysis。
        """

        data = self._parse_json(json_text)

        patch = self._build_patch(data)
        insights = self._build_insights(data)
        decision_feedback = self._build_decision_feedback(data)
        patch = self._protect_commute_preference(
            patch,
            decision_feedback,
            latest_user_message,
        )

        return ProfileAnalysis(
            patch=patch,
            insights=insights,
            decision_feedback=decision_feedback,
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
            raise TypeError(
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

    def _build_decision_feedback(
        self,
        data: dict,
    ) -> DecisionRelevantFeedback:
        raw_feedback = data.get("decision_relevant_feedback")
        if not isinstance(raw_feedback, dict):
            return NO_DECISION_FEEDBACK

        try:
            return DecisionRelevantFeedback.model_validate(raw_feedback)
        except (TypeError, ValueError):
            return NO_DECISION_FEEDBACK

    @staticmethod
    def _protect_commute_preference(
        patch: LivingProfilePatch,
        feedback: DecisionRelevantFeedback,
        latest_user_message: str,
    ) -> LivingProfilePatch:
        if (
            not feedback.relevant
            or feedback.observed_commute_minutes is None
            or patch.commute_minutes != feedback.observed_commute_minutes
        ):
            return patch

        explicit_preference = re.search(
            r"(?:最多|最大|上限|只能接受|最多接受|希望|控制在).{0,12}\d+\s*分钟",
            latest_user_message,
        )
        if explicit_preference is not None:
            return patch

        return replace(patch, commute_minutes=None)


profile_intelligence = ProfileIntelligence()
