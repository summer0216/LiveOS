from pydantic import ValidationError

from app.core.ai_client import ai_client
from app.core.logger import logger
from app.runtime.decision import build_decision_prompt
from app.schemas.decision import (
    DecisionInput,
    DecisionReason,
    DecisionResult,
    DecisionTradeOff,
    PropertyDecisionInput,
)
from app.services.commute_evidence import CommuteEvidence, get_commute_evidence
from app.services.decision_context_builder import decision_context_builder
from app.services.decision_record_service import decision_record_service
from app.services.living_model_builder import living_model_builder
from app.services.nearby_rent_evidence import (
    NearbyRentEvidence,
    get_nearby_rent_evidence,
)
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


def apply_nearby_rent_evidence(
    result: DecisionResult,
    evidence: NearbyRentEvidence | None,
    budget: int | None,
) -> DecisionResult:
    if evidence is None or budget is None:
        return result

    if evidence.supports_budget(budget):
        evidence_reason = DecisionReason(
            title="附近独居租金证据",
            description=(
                f"{evidence.area}独立居住的已知租金约为 "
                f"{evidence.independent_min_rent}–{evidence.independent_max_rent} 元/月，"
                f"当前预算 {budget} 元在该范围内，独立居住方案可行。"
            ),
        )
        reasons = [
            reason
            for reason in result.reasons
            if "预算" not in reason.title
            and "合租" not in reason.title
            and "budget" not in reason.title.lower()
        ]
        return result.model_copy(
            update={
                "summary": (
                    f"根据附近租金证据，{budget} 元预算在 "
                    f"{evidence.independent_min_rent}–{evidence.independent_max_rent} 元的"
                    "独居租金范围内，独立居住方案可行。下一步应直接比较具体房源。"
                ),
                "reasons": [evidence_reason, *reasons][:4],
            }
        )

    evidence_reason = DecisionReason(
        title="附近独居租金证据",
        description=(
            f"{evidence.area}独立居住的已知租金约为 "
            f"{evidence.independent_min_rent}–{evidence.independent_max_rent} 元/月，"
            f"当前预算 {budget} 元不足以覆盖该范围。"
        ),
    )
    evidence_trade_off = DecisionTradeOff(
        title="独居预算取舍",
        description="若保持独居，应优先放宽通勤范围或提高预算；否则需要重新考虑合租或更小户型。",
    )
    reasons = [
        reason
        for reason in result.reasons
        if "预算" not in reason.title and "budget" not in reason.title.lower()
    ]
    reasons = [evidence_reason, *reasons][:4]
    trade_offs = [evidence_trade_off, *result.trade_offs][:3]
    summary = (
        "附近租金证据显示，当前预算暂不足以支持该区域的独居方案。"
        "建议先放宽通勤或调整预算，再比较具体房源。"
    )
    return result.model_copy(
        update={
            "summary": summary,
            "reasons": reasons,
            "trade_offs": trade_offs,
            "confidence": min(result.confidence or 0.0, 0.65),
        }
    )


def apply_grounded_tradeoff(
    result: DecisionResult,
    rent_evidence: NearbyRentEvidence | None,
    commute_evidence: CommuteEvidence | None,
    budget: int | None,
) -> DecisionResult:
    result = apply_nearby_rent_evidence(result, rent_evidence, budget)
    if (
        rent_evidence is None
        or commute_evidence is None
        or budget is None
        or not rent_evidence.supports_budget(budget)
    ):
        return result

    tradeoff_reason = DecisionReason(
        title="独居与通勤权衡",
        description=(
            f"附近独居租金约为 {rent_evidence.independent_min_rent}–"
            f"{rent_evidence.independent_max_rent} 元/月，{budget} 元预算可行；"
            f"但预计每日通勤约 {commute_evidence.commute_minutes} 分钟。"
        ),
    )
    tradeoff = DecisionTradeOff(
        title="独居与通勤取舍",
        description=(
            f"可以保持独立居住，但需要接受约 {commute_evidence.commute_minutes} 分钟通勤；"
            "如果通勤优先级更高，建议重新选择区域。"
        ),
    )
    reasons = [
        reason
        for reason in result.reasons
        if reason.title not in {"附近独居租金证据", "独居与通勤权衡"}
    ]
    return result.model_copy(
        update={
            "summary": (
                "独立居住可行，但需要接受约 "
                f"{commute_evidence.commute_minutes} 分钟通勤。"
                "如果通勤优先级高于独居，建议重新选择区域。"
            ),
            "reasons": [tradeoff_reason, *reasons][:4],
            "trade_offs": [tradeoff, *result.trade_offs][:3],
        }
    )


def build_next_actions(
    result: DecisionResult,
    rent_evidence: NearbyRentEvidence | None,
    commute_evidence: CommuteEvidence | None,
    budget: int | None,
) -> DecisionResult:
    if (
        result.status != "ready"
        or not result.summary
        or rent_evidence is None
        or commute_evidence is None
        or budget is None
        or not rent_evidence.supports_budget(budget)
        or "独立居住可行" not in result.summary
        or not any(
            trade_off.title == "独居与通勤取舍"
            and str(commute_evidence.commute_minutes) in trade_off.description
            for trade_off in result.trade_offs
        )
    ):
        return result

    next_actions = (
        f"下一步：优先比较{rent_evidence.area}约 {budget} 元的一居室。"
        f"如果不能接受约 {commute_evidence.commute_minutes} 分钟通勤，"
        "重新选择距离公司更近的区域；当前预算支持独立居住，暂不优先考虑合租。"
    )
    return result.model_copy(
        update={
            "summary": f"{result.summary} {next_actions}",
        }
    )


class DecisionService:
    def generate(self, conversation_id: str) -> DecisionResult:
        if not conversation_id:
            return waiting_decision("缺少有效的对话信息，暂时无法生成建议。")

        decision_context = decision_context_builder.build(
            conversation_id,
        )

        profile = profile_manager.get(conversation_id)

        if profile is None:
            return waiting_decision("请先完善 Living Profile。")

        properties = property_manager.list(conversation_id)

        if not properties:
            return waiting_decision("请先添加候选房源。")

        nearby_rent_evidence = get_nearby_rent_evidence(profile)
        commute_evidence = get_commute_evidence(profile)

        try:
            decision_input = DecisionInput(
                living_model=living_model_builder.build(
                    conversation_id,
                    profile,
                    decision_context.memory_context,
                ),
                properties=[
                    PropertyDecisionInput.model_validate(property_)
                    for property_ in properties
                ],
            )
            json_text = ai_client.generate_json(
                build_decision_prompt(
                    decision_input,
                    decision_context,
                    grounded_evidence="\n".join(
                        evidence.prompt_context()
                        for evidence in (
                            nearby_rent_evidence,
                            commute_evidence,
                        )
                        if evidence is not None
                    )
                    or None,
                ),
            )
            result = DecisionResult.model_validate_json(json_text)
        except (RuntimeError, ValidationError, ValueError) as error:
            logger.warning(
                "Decision generation failed for conversation %s: %s",
                conversation_id,
                error,
            )
            return waiting_decision("AI 暂时无法完成当前决策，请稍后重试。")

        result = apply_grounded_tradeoff(
            result,
            nearby_rent_evidence,
            commute_evidence,
            profile.budget,
        )
        result = build_next_actions(
            result,
            nearby_rent_evidence,
            commute_evidence,
            profile.budget,
        )

        if result.status == "waiting":
            return result

        property_ids = {
            property_.id for property_ in properties if property_.id is not None
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
        except Exception:  # noqa: BLE001 - Record persistence must not block a Ready Decision.
            logger.exception(
                "Failed to save Decision Record for conversation %s.",
                conversation_id,
            )

        return result


decision_service = DecisionService()
