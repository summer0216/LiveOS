from app.models.profile import LivingProfile
from app.runtime.decision import build_decision_prompt
from app.runtime.living_model import LivingModel, LivingModelProfile
from app.schemas.decision import (
    DecisionInput,
    DecisionReason,
    DecisionResult,
    DecisionTradeOff,
    PropertyDecisionInput,
)
from app.schemas.decision_context import DecisionContext
from app.services.commute_evidence import get_commute_evidence
from app.services.decision_service import (
    apply_grounded_tradeoff,
    apply_nearby_rent_evidence,
    build_next_actions,
    has_recoverable_primary_next,
)
from app.services.nearby_rent_evidence import get_nearby_rent_evidence


def make_decision_input() -> DecisionInput:
    return DecisionInput(
        living_model=LivingModel(
            conversation_id="grounded-decision",
            profile=LivingModelProfile(
                work_location="成都高新区合作路89号",
                preferred_city="成都",
                budget=2200,
                family_size=1,
            ),
            decision_memory=[],
        ),
        properties=[
            PropertyDecisionInput(
                id="property-1",
                title="合作路附近独立一居",
                district="成都高新区",
                rent=2200,
            )
        ],
    )


def test_nearby_rent_evidence_is_retrieved_for_fixed_acceptance_scenario() -> None:
    evidence = get_nearby_rent_evidence(
        LivingProfile(
            work_location="成都高新区合作路89号",
            preferred_city="成都",
            budget=2200,
            family_size=1,
        )
    )

    assert evidence is not None
    assert evidence.area == "成都高新区合作路附近"
    assert evidence.independent_min_rent == 1900
    assert evidence.independent_max_rent == 2300


def test_grounded_evidence_enters_decision_prompt_as_authoritative_constraint() -> None:
    evidence = get_nearby_rent_evidence(
        LivingProfile(
            work_location="成都高新区合作路89号",
            preferred_city="成都",
            budget=2200,
            family_size=1,
        )
    )
    assert evidence is not None

    prompt = build_decision_prompt(
        make_decision_input(),
        DecisionContext(conversation_id="grounded-decision"),
        grounded_evidence=evidence.prompt_context(),
    )

    assert "GROUNDED EVIDENCE:" in prompt
    assert "1900-2300 RMB/month" in prompt
    assert "higher priority than model prior knowledge" in prompt


def test_grounded_evidence_changes_conflicting_decision() -> None:
    evidence = get_nearby_rent_evidence(
        LivingProfile(
            work_location="成都高新区合作路89号",
            preferred_city="成都",
            budget=2200,
            family_size=1,
        )
    )
    assert evidence is not None
    model_decision = DecisionResult(
        status="ready",
        summary="预算不足，建议考虑合租。",
        best_property_id="property-1",
        reasons=[
            DecisionReason(title="合租建议", description="根据模型先验，预算不足以独居。")
        ],
        confidence=0.9,
    )

    grounded = apply_nearby_rent_evidence(model_decision, evidence, 2200)

    assert grounded.summary != model_decision.summary
    assert "独立居住方案可行" in grounded.summary
    assert grounded.reasons[0].title == "附近独居租金证据"
    assert all("合租" not in reason.title for reason in grounded.reasons)


def test_multi_evidence_produces_one_tradeoff_decision() -> None:
    profile = LivingProfile(
        work_location="成都高新区合作路89号",
        preferred_city="成都",
        budget=2200,
        family_size=1,
    )
    rent_evidence = get_nearby_rent_evidence(profile)
    commute_evidence = get_commute_evidence(profile)
    assert rent_evidence is not None
    assert commute_evidence is not None
    assert commute_evidence.commute_minutes == 65

    model_decision = DecisionResult(
        status="ready",
        summary="预算不足，建议考虑合租。",
        best_property_id="property-1",
        reasons=[DecisionReason(title="模型判断", description="需要进一步收集信息。")],
        confidence=0.9,
    )

    grounded = apply_grounded_tradeoff(
        model_decision,
        rent_evidence,
        commute_evidence,
        2200,
    )

    assert "独立居住可行" in grounded.summary
    assert "65 分钟通勤" in grounded.summary
    assert "重新选择区域" in grounded.summary
    assert grounded.reasons[0].title == "独居与通勤权衡"
    assert grounded.trade_offs[0].title == "独居与通勤取舍"
    assert grounded.decision_gap == "约 65 分钟的工作日高峰通勤是否在实际体验中可以接受。"

    recommendation = build_next_actions(
        grounded,
        rent_evidence,
        commute_evidence,
        2200,
    )

    assert recommendation.summary is not None
    decision, primary_action = recommendation.summary.split("下一步：", 1)
    assert decision.strip() == grounded.summary
    assert primary_action == "先验证一次工作日高峰通勤，确认约 65 分钟是否可以接受。"
    assert "重新选择区域" not in primary_action
    assert "合租" not in primary_action
    assert "65 分钟" in grounded.decision_gap


def test_next_actions_do_not_ignore_conflicting_decision() -> None:
    profile = LivingProfile(
        work_location="成都高新区合作路89号",
        preferred_city="成都",
        budget=2200,
        family_size=1,
    )
    rent_evidence = get_nearby_rent_evidence(profile)
    commute_evidence = get_commute_evidence(profile)
    assert rent_evidence is not None
    assert commute_evidence is not None

    conflicting_decision = DecisionResult(
        status="ready",
        summary="当前信息不足以确认独立居住方案。",
        best_property_id="property-1",
        reasons=[DecisionReason(title="待确认", description="需要更多信息。")],
        trade_offs=[],
        confidence=0.5,
    )

    recommendation = build_next_actions(
        conflicting_decision,
        rent_evidence,
        commute_evidence,
        2200,
    )

    assert recommendation.summary is not None
    decision, primary_action = recommendation.summary.split("下一步：", 1)
    assert decision.strip() == conflicting_decision.summary
    assert "核实当前推荐房源" in primary_action
    assert "验证一次工作日高峰通勤" not in primary_action
    assert recommendation.summary.count("下一步：") == 1


def test_ordinary_ready_gets_one_decision_aligned_primary_next() -> None:
    result = DecisionResult(
        status="ready",
        summary="当前房源整体匹配，但城市信息仍需确认。",
        best_property_id="property-1",
        reasons=[DecisionReason(title="当前匹配", description="预算和通勤符合要求。")],
        trade_offs=[
            DecisionTradeOff(
                title="城市信息缺失",
                description="需要确认房源所在城市。",
            )
        ],
        confidence=0.7,
        decision_gap="房源所在城市是否满足当前生活范围。",
    )

    recommendation = build_next_actions(result, None, None, 3500)

    assert recommendation.summary is not None
    assert recommendation.summary.count("下一步：") == 1
    assert "房源所在城市是否满足当前生活范围" in recommendation.summary
    assert has_recoverable_primary_next(recommendation.summary)


def test_existing_primary_next_is_not_duplicated() -> None:
    result = DecisionResult(
        status="ready",
        summary="当前房源可以继续考虑。下一步：核实房源城市信息。",
        best_property_id="property-1",
        reasons=[DecisionReason(title="当前匹配", description="预算和通勤符合要求。")],
        confidence=0.7,
    )

    recommendation = build_next_actions(result, None, None, 3500)

    assert recommendation == result
    assert recommendation.summary is not None
    assert recommendation.summary.count("下一步：") == 1


def test_fact_gap_drives_a_concrete_reality_check() -> None:
    result = DecisionResult(
        status="ready",
        summary="当前房源可以继续考虑。",
        best_property_id="property-1",
        reasons=[DecisionReason(title="通勤预估", description="平台预估可接受。")],
        confidence=0.7,
        decision_gap="工作日高峰门到门通勤是否接近当前预估。",
    )

    recommendation = build_next_actions(result, None, None, None)

    assert recommendation.summary is not None
    assert recommendation.summary.count("下一步：") == 1
    assert "工作日高峰门到门通勤" in recommendation.summary
    assert "针对性核实" in recommendation.summary


def test_preference_gap_drives_preference_clarification() -> None:
    result = DecisionResult(
        status="ready",
        summary="当前方案暂时可行。",
        best_property_id="property-1",
        reasons=[DecisionReason(title="当前条件", description="预算可支持候选房源。")],
        confidence=0.7,
        decision_gap="独居空间与更短通勤之间的优先级是否需要调整。",
    )

    recommendation = build_next_actions(result, None, None, None)

    assert recommendation.summary is not None
    assert recommendation.summary.count("下一步：") == 1
    assert "独居空间与更短通勤之间的优先级" in recommendation.summary
    assert "明确" in recommendation.summary


def test_waiting_decision_does_not_require_primary_next() -> None:
    result = DecisionResult(
        status="waiting",
        summary="当前信息不足，需要进一步确认候选对象。",
    )

    assert build_next_actions(result, None, None, None) == result
