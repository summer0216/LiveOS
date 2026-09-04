import re

from pydantic import ValidationError

from app.core.ai_client import ai_client
from app.core.logger import logger
from app.models.action_progress import (
    ActionProgressStatus,
    CurrentActionProgress,
    LatestVerifiedAction,
    VerificationOutcomeStatus,
)
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
    if any(marker in decision_gap for marker in ("优先级", "取舍", "是否愿意")):
        return True
    return bool(
        re.search(
            r"(?:哪(?:个|项|种).{0,16}(?:重要|看重|愿意接受|难接受)|"
            r"(?:更|最)(?:看重|重视|在意|愿意接受|难以接受|无法接受)"
            r".{0,36}(?:还是|或|哪(?:个|项|种))|"
            r"宁愿.{0,20}(?:牺牲|放弃)|"
            r"是否接受.{0,24}(?:换取|牺牲|放弃))",
            decision_gap,
        )
    )


def repeats_resolved_verification(
    result: DecisionResult,
    current_action: CurrentActionProgress | None,
) -> bool:
    if (
        result.status != "ready"
        or not result.summary
        or not result.decision_gap
        or current_action is None
        or current_action.status != ActionProgressStatus.COMPLETED
        or current_action.outcome_status is None
        or not current_action.verification_evidence
    ):
        return False

    primary_next = result.summary.split(PRIMARY_NEXT_DELIMITER, 1)[-1]
    normalized_previous = re.sub(r"\s+", "", current_action.next_text)
    normalized_current = re.sub(
        r"\s+",
        "",
        f"{result.decision_gap}{primary_next}",
    )
    if normalized_previous and normalized_previous in normalized_current:
        return True

    topic_markers = {
        "commute_minutes": ("通勤", "路程", "门到门"),
        "city": ("城市", "位置", "所在"),
        "rent": ("租金", "房租", "费用"),
    }
    evidence_topics = {
        marker
        for evidence in current_action.verification_evidence
        for marker in topic_markers.get(evidence.field, ())
    }
    if not evidence_topics:
        return False

    new_target_markers = (
        "新候选",
        "新的候选",
        "备选",
        "另一候选",
        "替代候选",
        "调整后的",
    )
    if any(marker in result.decision_gap for marker in new_target_markers):
        return False

    verification_markers = (
        "核实",
        "验证",
        "确认",
        "实测",
        "测试",
        "查看",
        "询问",
        "尚未",
        "仍需",
        "再测",
    )
    next_repeats = any(marker in primary_next for marker in evidence_topics) and any(
        marker in primary_next for marker in verification_markers
    )
    gap_repeats = (
        not _is_preference_gap(result.decision_gap)
        and any(marker in result.decision_gap for marker in evidence_topics)
        and any(
            marker in result.decision_gap
            for marker in ("是否", "尚未", "未确认", "仍需", "需确认")
        )
    )
    return next_repeats or gap_repeats


def _fallback_primary_next(result: DecisionResult) -> str:
    if result.decision_gap:
        if _is_preference_gap(result.decision_gap):
            return (
                f"{PRIMARY_NEXT_DELIMITER}围绕“{result.decision_gap}”做一次二选一取舍："
                "分别设想长期承受两种代价，选出更难接受的一项，"
                "再用这个结果确定当前优先方向。"
            )
        if "通勤" in result.decision_gap:
            return (
                f"{PRIMARY_NEXT_DELIMITER}围绕“{result.decision_gap}”完成一次有代表性的"
                "门到门通勤实测，记录总时长和主要阻碍，再将结果与当前可接受范围对照。"
            )
        return (
            f"{PRIMARY_NEXT_DELIMITER}围绕“{result.decision_gap}”完成一次直接核实，"
            "记录能够判断该条件是否成立的实际结果，再与当前要求对照。"
        )
    if result.trade_offs:
        return (
            f"{PRIMARY_NEXT_DELIMITER}针对“{result.trade_offs[0].title}”完成一次直接核实，"
            "记录能够判断该取舍是否可接受的实际结果，再决定是否继续当前方案。"
        )
    return (
        f"{PRIMARY_NEXT_DELIMITER}实地核实当前推荐房源最影响判断的居住条件，"
        "记录是否符合当前需求，再决定是否继续该方案。"
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


def _rejects_longer_commute(
    verified_reality: CurrentActionProgress | LatestVerifiedAction | None,
) -> bool:
    if (
        verified_reality is None
        or verified_reality.status != ActionProgressStatus.COMPLETED
        or verified_reality.outcome_status != VerificationOutcomeStatus.DISCONFIRMED
    ):
        return False
    rejection_markers = ("无法接受", "不能接受", "接受不了", "不可接受")
    return any(
        evidence.field == "commute_minutes"
        and any(marker in evidence.statement for marker in rejection_markers)
        for evidence in verified_reality.verification_evidence
    )


def apply_nearby_rent_evidence(
    result: DecisionResult,
    evidence: NearbyRentEvidence | None,
    budget: int | None,
    verified_reality: CurrentActionProgress | LatestVerifiedAction | None = None,
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
    longer_commute_rejected = _rejects_longer_commute(verified_reality)
    evidence_trade_off = DecisionTradeOff(
        title="独居预算取舍",
        description=(
            "已确认更长通勤不可接受；若保持当前通勤边界和独居，应提高预算，"
            "否则需要调整住房形式。"
            if longer_commute_rejected
            else "若保持独居，应优先放宽通勤范围或提高预算；否则需要重新考虑合租或更小户型。"
        ),
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
        + (
            "已确认更长通勤不可接受，应优先评估提高预算或调整住房形式。"
            if longer_commute_rejected
            else "建议先放宽通勤或调整预算，再比较具体房源。"
        )
    )
    return result.model_copy(
        update={
            "summary": summary,
            "reasons": reasons,
            "trade_offs": trade_offs,
            "confidence": min(result.confidence or 0.0, 0.65),
            "decision_gap": (
                "是否愿意提高预算或调整住房形式以维持当前通勤边界。"
                if longer_commute_rejected
                else "是否愿意放宽通勤范围或调整预算以维持独立居住。"
            ),
        }
    )


def apply_grounded_tradeoff(
    result: DecisionResult,
    rent_evidence: NearbyRentEvidence | None,
    commute_evidence: CommuteEvidence | None,
    budget: int | None,
    verified_reality: CurrentActionProgress | LatestVerifiedAction | None = None,
) -> DecisionResult:
    result = apply_nearby_rent_evidence(
        result,
        rent_evidence,
        budget,
        verified_reality,
    )
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
                "下一步：选择一个通勤明确短于当前方案的备选区域，"
                f"核对其门到门通勤是否比已拒绝的约 {observed_minutes} 分钟明显改善，"
                "再决定是否替换当前区域。"
            )
        else:
            next_action = (
                "下一步：选择一套当前区域内符合预算的具体房源，"
                "核实其最影响居住的实际条件是否满足当前需求，再决定是否继续。"
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
        "下一步：完成一次有代表性的工作日高峰门到门通勤，"
        f"记录总时长和主要阻碍，并确认约 {commute_evidence.commute_minutes} 分钟"
        "是否在实际体验中可以接受。"
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
            decision_action_progress_service.latest_verified_state(
                conversation_id
            ),
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

        if repeats_resolved_verification(result, decision_context.current_action):
            logger.warning(
                "Ready Decision repeated a resolved verification for conversation %s.",
                conversation_id,
            )
            return waiting_decision(
                "当前验证已经完成，LiveOS 正在根据新的现实重新形成下一步。"
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
