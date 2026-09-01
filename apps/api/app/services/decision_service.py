import re

from pydantic import ValidationError

from app.core.ai_client import ai_client
from app.core.logger import logger
from app.models.decision_feedback import DecisionRelevantFeedback
from app.runtime.decision import build_decision_prompt
from app.schemas.decision import (
    DecisionInput,
    DecisionReason,
    DecisionResult,
    DecisionTradeOff,
    PropertyDecisionInput,
)
from app.services.commute_evidence import CommuteEvidence, get_commute_evidence
from app.services.decision_action_progress import decision_action_progress_service
from app.services.decision_context_builder import decision_context_builder
from app.services.decision_record_service import decision_record_service
from app.services.living_model_builder import living_model_builder
from app.services.nearby_rent_evidence import (
    NearbyRentEvidence,
    get_nearby_rent_evidence,
)
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager

PRIMARY_NEXT_DELIMITER = "下一步："


def has_recoverable_primary_next(summary: str | None) -> bool:
    if summary is None or summary.count(PRIMARY_NEXT_DELIMITER) != 1:
        return False
    decision_text, next_text = summary.split(PRIMARY_NEXT_DELIMITER, 1)
    if not decision_text.strip() or not next_text.strip():
        return False
    return not bool(re.search(r"\n|(?:^|\s)[1-9][.、)]|[•·]", next_text))


def _decision_without_primary_next(summary: str) -> str:
    return summary.split(PRIMARY_NEXT_DELIMITER, 1)[0].strip()


def _is_preference_gap(decision_gap: str) -> bool:
    return any(
        marker in decision_gap
        for marker in ("优先级", "取舍", "是否愿意", "是否接受", "接受范围")
    )


def _fallback_primary_next(result: DecisionResult) -> str:
    if result.decision_gap:
        if _is_preference_gap(result.decision_gap):
            return (
                f"{PRIMARY_NEXT_DELIMITER}先明确“{result.decision_gap}”的取舍优先级，"
                "再决定是否继续当前方案。"
            )
        return (
            f"{PRIMARY_NEXT_DELIMITER}优先围绕“{result.decision_gap}”完成一次针对性核实，"
            "再决定是否继续当前方案。"
        )
    if result.trade_offs:
        return (
            f"{PRIMARY_NEXT_DELIMITER}核实“{result.trade_offs[0].title}”对应的关键信息，"
            "再决定是否继续当前方案。"
        )
    return (
        f"{PRIMARY_NEXT_DELIMITER}核实当前推荐房源的实际条件，"
        "再决定是否继续该方案。"
    )


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
                "decision_gap": "当前候选房源的实际租金和居住条件是否符合预期。",
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
            "decision_gap": "是否愿意放宽通勤范围或调整预算以维持独立居住。",
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
            "decision_gap": (
                f"约 {commute_evidence.commute_minutes} 分钟的工作日高峰通勤"
                "是否在实际体验中可以接受。"
            ),
        }
    )


def build_next_actions(
    result: DecisionResult,
    rent_evidence: NearbyRentEvidence | None,
    commute_evidence: CommuteEvidence | None,
    budget: int | None,
    current_feedback: DecisionRelevantFeedback | None = None,
) -> DecisionResult:
    if result.status != "ready" or not result.summary:
        return result

    if has_recoverable_primary_next(result.summary):
        return result

    if (
        current_feedback is not None
        and current_feedback.relevant
        and current_feedback.observed_commute_minutes is not None
    ):
        observed_minutes = current_feedback.observed_commute_minutes
        if current_feedback.judgment == "unacceptable":
            next_action = (
                "下一步：优先比较通勤时间更短的备选区域，"
                f"先排除实测通勤约 {observed_minutes} 分钟的方案。"
            )
        else:
            next_action = (
                "下一步：继续比较当前区域的具体房源，"
                "优先核实租金和房源条件。"
            )
        decision_text = _decision_without_primary_next(result.summary)
        return result.model_copy(update={"summary": f"{decision_text} {next_action}"})

    if (
        rent_evidence is None
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
        decision_text = _decision_without_primary_next(result.summary)
        return result.model_copy(
            update={
                "summary": f"{decision_text} {_fallback_primary_next(result)}",
            }
        )

    next_actions = (
        "下一步：先验证一次工作日高峰通勤，"
        f"确认约 {commute_evidence.commute_minutes} 分钟是否可以接受。"
    )
    return result.model_copy(
        update={
            "summary": f"{result.summary} {next_actions}",
        }
    )


def apply_decision_feedback(
    result: DecisionResult,
    feedback: DecisionRelevantFeedback | None,
) -> DecisionResult:
    if (
        result.status != "ready"
        or feedback is None
        or not feedback.relevant
        or feedback.observed_commute_minutes is None
    ):
        return result

    observed_minutes = feedback.observed_commute_minutes
    feedback_reason = DecisionReason(
        title="实际通勤反馈",
        description=feedback.observation or f"实测通勤约 {observed_minutes} 分钟。",
    )
    remaining_reasons = [
        reason for reason in result.reasons if reason.title != "实际通勤反馈"
    ]

    if feedback.judgment == "unacceptable":
        summary = (
            f"实测通勤约 {observed_minutes} 分钟且无法接受，"
            "当前区域方案不再适合，应优先重新选择通勤更短的区域。"
        )
        trade_off = DecisionTradeOff(
            title="独居与实际通勤取舍",
            description=(
                f"独立居住仍可能可行，但实测约 {observed_minutes} 分钟通勤已被明确拒绝，"
                "当前应优先调整区域。"
            ),
        )
        decision_gap = "通勤更短的备选区域是否能在实际体验中满足你的接受范围。"
    else:
        summary = (
            f"实测约 {observed_minutes} 分钟通勤且可以接受，"
            "当前独立居住方向可以继续，再比较具体房源条件。"
        )
        trade_off = DecisionTradeOff(
            title="独居与实际通勤取舍",
            description=(
                f"用户已确认可以接受实测约 {observed_minutes} 分钟通勤，"
                "当前无需仅因通勤放弃独立居住方向。"
            ),
        )
        decision_gap = "当前区域候选房源的租金和居住条件是否符合实际预期。"

    return result.model_copy(
        update={
            "summary": summary,
            "reasons": [feedback_reason, *remaining_reasons][:4],
            "trade_offs": [trade_off, *result.trade_offs][:3],
            "decision_gap": decision_gap,
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

        if result.status == "waiting":
            return result

        result = apply_grounded_tradeoff(
            result,
            nearby_rent_evidence,
            commute_evidence,
            profile.budget,
        )
        result = apply_decision_feedback(
            result,
            decision_context.current_feedback,
        )
        result = build_next_actions(
            result,
            nearby_rent_evidence,
            commute_evidence,
            profile.budget,
            decision_context.current_feedback,
        )

        if result.decision_gap is None or not result.decision_gap.strip():
            logger.warning(
                "Ready Decision has no Decision Gap for conversation %s.",
                conversation_id,
            )
            return waiting_decision("AI 暂时无法明确当前最关键的未知，请稍后重试。")

        if not has_recoverable_primary_next(result.summary):
            logger.warning(
                "Ready Decision has no recoverable Primary NEXT for conversation %s.",
                conversation_id,
            )
            return waiting_decision("AI 暂时无法形成可执行的下一步，请稍后重试。")

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
            record = decision_record_service.save(
                conversation_id=conversation_id,
                decision=result,
            )
            decision_action_progress_service.reconcile_ready_record(record)
        except Exception:  # noqa: BLE001 - Record persistence must not block a Ready Decision.
            logger.exception(
                "Failed to save Decision Record or Action State for conversation %s.",
                conversation_id,
            )

        return result


decision_service = DecisionService()
