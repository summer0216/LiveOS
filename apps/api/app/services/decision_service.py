from pydantic import ValidationError

from app.core.ai_client import ai_client
from app.core.logger import logger
from app.runtime.decision import build_decision_prompt
from app.schemas.decision import (
    DecisionInput,
    DecisionResult,
    LivingProfileDecisionInput,
    PropertyDecisionInput,
)
from app.services.decision_context_service import decision_context_service
from app.services.decision_record_service import decision_record_service
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager


def waiting_decision(summary: str) -> DecisionResult:
    return DecisionResult(
        status="waiting",
        summary=summary,
        best_property_id=None,
        reasons=[],
        trade_offs=[],
        confidence=None,
    )


class DecisionService:
    def generate(self, conversation_id: str) -> DecisionResult:
        if not conversation_id:
            return waiting_decision("缺少有效的对话信息，暂时无法生成建议。")

        decision_context_service.build_context(conversation_id)

        profile = profile_manager.get(conversation_id)

        if profile is None:
            return waiting_decision("请先完善 Living Profile。")

        properties = property_manager.list(conversation_id)

        if not properties:
            return waiting_decision("请先添加候选房源。")

        try:
            decision_input = DecisionInput(
                living_profile=LivingProfileDecisionInput.model_validate(
                    profile,
                ),
                properties=[
                    PropertyDecisionInput.model_validate(property_)
                    for property_ in properties
                ],
            )
            json_text = ai_client.generate_json(
                build_decision_prompt(decision_input),
            )
            result = DecisionResult.model_validate_json(json_text)
        except (RuntimeError, ValidationError, ValueError) as error:
            logger.warning(
                "Decision generation failed for conversation %s: %s",
                conversation_id,
                error,
            )
            return waiting_decision("AI 暂时无法完成当前决策，请稍后重试。")

        if result.status == "waiting":
            return result

        property_ids = {
            property_.id
            for property_ in properties
            if property_.id is not None
        }

        if result.best_property_id not in property_ids:
            logger.warning(
                "Decision returned an unknown property for conversation %s.",
                conversation_id,
            )
            return waiting_decision("AI 暂时无法验证推荐房源，请稍后重试。")

        try:
            decision_record_service.save(
                conversation_id=conversation_id,
                decision=result,
            )
        except Exception:
            logger.exception(
                "Failed to save Decision Record for conversation %s.",
                conversation_id,
            )

        return result


decision_service = DecisionService()
