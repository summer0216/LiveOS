from app.models.profile import LivingProfile
from app.runtime.decision import build_decision_prompt
from app.runtime.living_model import LivingModel, LivingModelProfile
from app.schemas.decision import (
    DecisionInput,
    DecisionReason,
    DecisionResult,
    PropertyDecisionInput,
)
from app.schemas.decision_context import DecisionContext
from app.services.commute_evidence import get_commute_evidence
from app.services.decision_service import (
    apply_grounded_tradeoff,
    apply_nearby_rent_evidence,
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
