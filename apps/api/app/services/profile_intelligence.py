import json
import re
from dataclasses import replace

from app.core.ai_client import ai_client
from app.models.conversation import ConversationMessage
from app.models.decision_challenge import (
    NO_DECISION_CHALLENGE,
    DecisionChallenge,
)
from app.models.decision_feedback import (
    NO_DECISION_FEEDBACK,
    DecisionRelevantFeedback,
)
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import PROFILE_FIELDS, LivingProfilePatch, ProfileField
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
        patch = self._protect_explicit_clears(patch, latest_user_message)
        insights = self._build_insights(data)
        decision_feedback = self._build_decision_feedback(data)
        decision_challenge = self._build_decision_challenge(
            data,
            latest_user_message,
        )
        decision_feedback = self._protect_challenge_feedback(
            decision_feedback,
            decision_challenge,
            latest_user_message,
        )
        patch = self._protect_commute_preference(
            patch,
            decision_feedback,
            latest_user_message,
        )
        patch = self._protect_challenge_profile(
            patch,
            decision_challenge,
            latest_user_message,
        )

        return ProfileAnalysis(
            patch=patch,
            insights=insights,
            decision_feedback=decision_feedback,
            decision_challenge=decision_challenge,
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

        raw_clear_fields = data.get("clear_fields")
        clear_fields: frozenset[ProfileField] = frozenset(
            field
            for field in (
                raw_clear_fields if isinstance(raw_clear_fields, list) else []
            )
            if field in PROFILE_FIELDS
        )

        values = {
            "work_location": data.get("work_location"),
            "budget": data.get("budget"),
            "commute_minutes": data.get("commute_minutes"),
            "preferred_city": data.get("preferred_city"),
            "family_size": data.get("family_size"),
            "has_pet": data.get("has_pet"),
        }
        for field in clear_fields:
            values[field] = None

        return LivingProfilePatch(
            **values,
            clear_fields=clear_fields,
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

    def _build_decision_challenge(
        self,
        data: dict,
        latest_user_message: str,
    ) -> DecisionChallenge:
        raw_challenge = data.get("decision_challenge")
        if isinstance(raw_challenge, dict):
            try:
                challenge = DecisionChallenge.model_validate(raw_challenge)
                if challenge.relevant:
                    return challenge
            except (TypeError, ValueError):
                pass

        message = latest_user_message.strip()
        kind: str | None = None
        subject: str | None = None
        if re.search(r"(?:取舍|权衡).*(?:不值得|不合理|太久)|太久.*(?:取舍|值得)", message):
            kind = "TRADE_OFF"
            subject = "当前取舍"
        elif re.search(r"(?:太|过度)(?:看重|强调|依赖)", message):
            kind = "PRIORITY"
            subject = "当前判断优先级"
        elif re.search(r"(?:更倾向|更想选|另一个房源|其他房源|别的房源)", message):
            kind = "ALTERNATIVE"
            subject = "备选房源"
        elif re.search(
            r"(?:不认同|不同意|不赞同|重新考虑|再考虑|"
            r"判断.{0,8}(?:有问题|不合理)|推荐.{0,8}(?:有问题|不合理))",
            message,
        ):
            kind = "DIRECT"
            subject = "当前判断"

        if kind is None:
            return NO_DECISION_CHALLENGE
        return DecisionChallenge(
            relevant=True,
            kind=kind,
            subject=subject,
            statement=message[:240],
        )

    @staticmethod
    def _protect_challenge_feedback(
        feedback: DecisionRelevantFeedback,
        challenge: DecisionChallenge,
        latest_user_message: str,
    ) -> DecisionRelevantFeedback:
        if not challenge.relevant or not feedback.relevant:
            return feedback
        observed_reality = re.search(
            r"实际|实测|试过|体验|走过|看过|去了|结果|当天|今天|早高峰",
            latest_user_message,
        )
        return feedback if observed_reality is not None else NO_DECISION_FEEDBACK

    @staticmethod
    def _protect_explicit_clears(
        patch: LivingProfilePatch,
        latest_user_message: str,
    ) -> LivingProfilePatch:
        if not patch.clear_fields:
            return patch

        explicit_clear = re.search(
            (
                r"取消|撤销|作废|不作数|不算了|先不设|不设限制|"
                r"没有明确要求|不确定|没想好|不要继续按|先不考虑"
            ),
            latest_user_message,
        )
        if explicit_clear is not None:
            return patch

        return replace(patch, clear_fields=frozenset())

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
            r"(?:最多|最大|上限|只能接受|最多接受|希望|控制在).{0,12}\d+\s*分钟|"
            r"通勤.{0,8}(?:改|调整|设|按|恢复|变成|为).{0,8}\d+\s*分钟",
            latest_user_message,
        )
        if explicit_preference is not None:
            return patch

        return replace(patch, commute_minutes=None)

    @staticmethod
    def _protect_challenge_profile(
        patch: LivingProfilePatch,
        challenge: DecisionChallenge,
        latest_user_message: str,
    ) -> LivingProfilePatch:
        if not challenge.relevant:
            return patch

        updates: dict[str, object] = {}
        explicit_commute_preference = re.search(
            r"(?:最多|最大|上限|只能接受|最多接受|希望|控制在).{0,12}\d+\s*分钟|"
            r"通勤.{0,8}(?:改|调整|设|按|恢复|变成|为).{0,8}\d+\s*分钟",
            latest_user_message,
        )
        if patch.commute_minutes is not None and explicit_commute_preference is None:
            updates["commute_minutes"] = None

        explicit_budget_change = re.search(
            r"预算.{0,10}(?:改|调整|设|定|按|恢复|提高|降低|增加|减少|变成|为).{0,10}\d+",
            latest_user_message,
        )
        if (
            challenge.kind == "PRIORITY"
            and patch.budget is not None
            and explicit_budget_change is None
        ):
            updates["budget"] = None

        return replace(patch, **updates) if updates else patch


profile_intelligence = ProfileIntelligence()
