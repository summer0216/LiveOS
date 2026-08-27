import json
import re
from dataclasses import replace

from app.core.ai_client import ai_client
from app.models.action_progress import (
    NO_ACTION_PROGRESS_UPDATE,
    NO_VERIFICATION_OUTCOME_UPDATE,
    ActionProgressStatus,
    ActionProgressUpdate,
    VerificationEvidence,
    VerificationOutcomeStatus,
    VerificationOutcomeUpdate,
)
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
        verification_outcome_update = self._build_verification_outcome_update(
            data,
            latest_user_message,
        )
        action_progress_update = self._build_action_progress_update(
            data,
            latest_user_message,
        )
        if verification_outcome_update.relevant:
            action_progress_update = ActionProgressUpdate(
                relevant=True,
                status=ActionProgressStatus.COMPLETED,
            )
        decision_challenge = self._protect_action_progress_challenge(
            decision_challenge,
            action_progress_update,
            latest_user_message,
        )
        decision_feedback = self._protect_challenge_feedback(
            decision_feedback,
            decision_challenge,
            latest_user_message,
        )
        decision_feedback = self._protect_action_progress_feedback(
            decision_feedback,
            action_progress_update,
            latest_user_message,
        )
        decision_feedback = self._protect_verification_feedback(
            decision_feedback,
            verification_outcome_update,
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
        patch = self._protect_verification_profile(
            patch,
            verification_outcome_update,
            latest_user_message,
        )

        return ProfileAnalysis(
            patch=patch,
            insights=insights,
            decision_feedback=decision_feedback,
            decision_challenge=decision_challenge,
            action_progress_update=action_progress_update,
            verification_outcome_update=verification_outcome_update,
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

    def _build_verification_outcome_update(
        self,
        data: dict,
        latest_user_message: str,
    ) -> VerificationOutcomeUpdate:
        message = latest_user_message.strip()
        status = self._explicit_verification_outcome_status(message)
        if status is None:
            return NO_VERIFICATION_OUTCOME_UPDATE

        deterministic_evidence = self._verification_evidence(message)
        raw_update = data.get("verification_outcome_update")
        if isinstance(raw_update, dict):
            try:
                parsed = VerificationOutcomeUpdate.model_validate(raw_update)
                if parsed.relevant and parsed.status == status:
                    return parsed.model_copy(
                        update={"evidence": deterministic_evidence or parsed.evidence}
                    )
            except (TypeError, ValueError):
                pass

        return VerificationOutcomeUpdate(
            relevant=True,
            status=status,
            evidence=deterministic_evidence,
        )

    @staticmethod
    def _explicit_verification_outcome_status(
        message: str,
    ) -> VerificationOutcomeStatus | None:
        if re.search(r"好像|听说|可能|也许|或许", message):
            return None
        if re.search(r"确认不了|无法确认|没法确认|不能确认|也不知道|也不清楚", message):
            return VerificationOutcomeStatus.INCONCLUSIVE
        if re.search(
            r"(?:确认(?:过)?了|核实(?:过)?了|查证(?:过)?了|试过了).{0,40}"
            r"(?:不在|不是|不对|错误|有误|接受不了|不能接受|不接受)",
            message,
        ) or re.search(r"实际.{0,12}\d+\s*分钟.{0,20}最多只能接受", message):
            return VerificationOutcomeStatus.DISCONFIRMED
        if re.search(
            r"(?:确认(?:过)?了|核实(?:过)?了|查证(?:过)?了).{0,40}"
            r"(?:就在|确实|位于|租金|房租|通勤|实际|是)",
            message,
        ):
            return VerificationOutcomeStatus.CONFIRMED
        return None

    @staticmethod
    def _verification_evidence(message: str) -> tuple[VerificationEvidence, ...]:
        evidence: list[VerificationEvidence] = []
        commute = re.search(
            r"实际.{0,10}?(\d+)\s*分钟|(?:实测|跑下来).{0,8}?(\d+)\s*分钟",
            message,
        )
        if commute is not None:
            minutes = int(next(value for value in commute.groups() if value))
            evidence.append(
                VerificationEvidence(
                    field="commute_minutes",
                    value=minutes,
                    statement=message[:500],
                )
            )

        rent = re.search(r"(?:租金|房租|实际租金).{0,8}?(\d+)\s*元", message)
        if rent is not None:
            evidence.append(
                VerificationEvidence(
                    field="rent",
                    value=int(rent.group(1)),
                    statement=message[:500],
                )
            )

        cities = re.findall(
            r"(?<!不)(?:就在|位于|在)([\u4e00-\u9fff]{2,12})",
            message,
        )
        if cities:
            evidence.append(
                VerificationEvidence(
                    field="city",
                    value=cities[-1],
                    statement=message[:500],
                )
            )

        if not evidence:
            evidence.append(
                VerificationEvidence(
                    field="statement",
                    value=message[:240],
                    statement=message[:500],
                )
            )
        return tuple(evidence[:4])

    def _build_action_progress_update(
        self,
        data: dict,
        latest_user_message: str,
    ) -> ActionProgressUpdate:
        message = latest_user_message.strip()
        deterministic_status = self._explicit_action_progress_status(message)
        if deterministic_status is not None:
            return ActionProgressUpdate(
                relevant=True,
                status=deterministic_status,
            )

        raw_update = data.get("action_progress_update")
        if not isinstance(raw_update, dict):
            return NO_ACTION_PROGRESS_UPDATE
        try:
            update = ActionProgressUpdate.model_validate(raw_update)
        except (TypeError, ValueError):
            return NO_ACTION_PROGRESS_UPDATE
        if not update.relevant or update.status is None:
            return NO_ACTION_PROGRESS_UPDATE
        if not self._has_explicit_action_evidence(update.status, message):
            return NO_ACTION_PROGRESS_UPDATE
        return update

    @staticmethod
    def _explicit_action_progress_status(
        message: str,
    ) -> ActionProgressStatus | None:
        if re.search(r"还没|尚未|没来得及|其实没(?:去|试|看|开始|做)", message):
            return ActionProgressStatus.NOT_STARTED
        if re.search(r"不打算|先不做|不准备再|不想再|不再(?:去|试|看|做)", message):
            return ActionProgressStatus.ABANDONED
        if re.search(
            r"已经.{0,12}(?:去|试|看|查|问|确认|核实|跑|走|做|完成)|"
            r"(?:去|试|看|查|问|确认|核实|跑|走|做)过|"
            r"(?:确认|核实|查证)(?:过)?了|"
            r"实际.{0,10}(?:跑|走|试|看).{0,8}(?:一遍|一次)",
            message,
        ):
            return ActionProgressStatus.COMPLETED
        if re.search(r"也许|可能|或许", message):
            return None
        if re.search(
            r"(?:明天|后天|周末|下班后|今晚|明早|早上).{0,14}(?:去|试|看|跑|走|做)|"
            r"(?:准备|打算|计划|决定|会|要).{0,8}(?:去|试|看|跑|走|做)",
            message,
        ):
            return ActionProgressStatus.PLANNED
        return None

    @classmethod
    def _has_explicit_action_evidence(
        cls,
        status: ActionProgressStatus,
        message: str,
    ) -> bool:
        return cls._explicit_action_progress_status(message) == status

    @staticmethod
    def _protect_action_progress_feedback(
        feedback: DecisionRelevantFeedback,
        update: ActionProgressUpdate,
        latest_user_message: str,
    ) -> DecisionRelevantFeedback:
        if not update.relevant or not feedback.relevant:
            return feedback
        has_decision_outcome = re.search(
            r"\d+\s*分钟|接受不了|不能接受|不接受|可以接受|能接受|太久|"
            r"结果|实际.{0,10}\d+",
            latest_user_message,
        )
        return feedback if has_decision_outcome is not None else NO_DECISION_FEEDBACK

    @staticmethod
    def _protect_verification_feedback(
        feedback: DecisionRelevantFeedback,
        outcome: VerificationOutcomeUpdate,
        latest_user_message: str,
    ) -> DecisionRelevantFeedback:
        if not outcome.relevant or not feedback.relevant:
            return feedback
        has_feedback_semantics = (
            feedback.observed_commute_minutes is not None
            or feedback.judgment is not None
            or re.search(
                r"接受不了|不能接受|不接受|可以接受|能接受|太久|实际.{0,10}\d+",
                latest_user_message,
            )
            is not None
        )
        return feedback if has_feedback_semantics else NO_DECISION_FEEDBACK

    @staticmethod
    def _protect_verification_profile(
        patch: LivingProfilePatch,
        outcome: VerificationOutcomeUpdate,
        latest_user_message: str,
    ) -> LivingProfilePatch:
        if not outcome.relevant:
            return patch

        explicit_profile_evidence = {
            "work_location": re.search(
                r"(?:我|本人).{0,8}(?:在|到).{1,20}(?:工作|上班)|"
                r"工作地点|上班地点",
                latest_user_message,
            ),
            "preferred_city": re.search(
                r"意向城市|想住|希望住|准备搬|打算搬",
                latest_user_message,
            ),
            "budget": re.search(
                r"预算.{0,10}\d+|(?:最多|上限|控制在).{0,8}\d+\s*元",
                latest_user_message,
            ),
            "commute_minutes": re.search(
                r"(?:最多|最大|上限|只能接受|最多接受|希望|控制在).{0,12}"
                r"\d+\s*分钟|通勤.{0,8}(?:改|调整|设|按|恢复|变成|为).{0,8}"
                r"\d+\s*分钟",
                latest_user_message,
            ),
            "family_size": re.search(
                r"(?:一家|家庭|我们).{0,8}\d+\s*人|\d+\s*人(?:住|居住)",
                latest_user_message,
            ),
            "has_pet": re.search(
                r"养宠物|有宠物|没有宠物|没宠物|不养宠物",
                latest_user_message,
            ),
        }
        updates: dict[str, object] = {
            field: None
            for field, evidence in explicit_profile_evidence.items()
            if evidence is None
        }
        clear_fields = set(patch.clear_fields)
        clear_fields.difference_update(updates)
        if updates or clear_fields != set(patch.clear_fields):
            updates["clear_fields"] = frozenset(clear_fields)
            return replace(patch, **updates)
        return patch

    @staticmethod
    def _protect_action_progress_challenge(
        challenge: DecisionChallenge,
        update: ActionProgressUpdate,
        latest_user_message: str,
    ) -> DecisionChallenge:
        if not update.relevant or not challenge.relevant:
            return challenge
        explicit_challenge = re.search(
            r"不认同|不同意|不赞同|重新考虑|再考虑|"
            r"判断.{0,8}(?:有问题|不合理)|推荐.{0,8}(?:有问题|不合理)",
            latest_user_message,
        )
        return challenge if explicit_challenge is not None else NO_DECISION_CHALLENGE

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
