import json

import pytest
from app.main import app
from app.models.profile import LivingProfile
from app.models.property import (
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
)
from app.schemas.property import PropertyResponse
from app.services.chat_service import _admit_canonical_rent_estimate
from app.services.living_meaning_service import (
    LivingMeaningService,
    living_meaning_service,
)
from app.services.property_manager import property_manager
from app.stores.runtime import profile_store
from fastapi.testclient import TestClient
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


class RentRangeIntelligence:
    meaning = "预计租金为每月1500至2500元，预算2000元处于区间内，实际租金仍待确认。"
    judgment = "预算与预计区间存在重叠，但实际月租未知，当前成本判断仍需保留不确定性。"
    unknown = "这处住所的实际月租是多少？"

    @staticmethod
    def grounding() -> list[dict[str, str]]:
        return [
            {
                "fact": "ESTIMATED_RENT_RANGE",
                "value": "1500-2500 CNY/month ESTIMATE",
            },
            {"fact": "BUDGET_REALITY", "value": "2000 CNY/month"},
        ]

    def generate_json(self, prompt: str, **_kwargs) -> str:
        assert '"RENT_REALITY"' not in prompt
        assert '"EXTERNAL_RENT_OBSERVATION"' not in prompt
        if "Audit whether EVERY claim" in prompt:
            assert "explicitly non-grounded estimate input" in prompt
            return json.dumps({"supported": True, "unsupported_claims": []})
        if "Judge whether the CURRENT Possible Life" in prompt:
            return json.dumps({
                "status": "NEED_MORE_REALITY",
                "reason": "预计区间已能与预算比较，但实际月租仍是必要的成本现实。",
                "meaning_reference": self.meaning,
                "judgment_reference": self.judgment,
                "grounding": self.grounding(),
            }, ensure_ascii=False)
        if "Judge whether this proposed Unknown" in prompt:
            return json.dumps({
                "question_reference": self.unknown,
                "judgment_reference": self.judgment,
                "current_reality_sufficient": False,
                "material_decision_change": True,
                "single_observable_fact": True,
                "impact_without_unsupported_bridge": True,
                "sufficient_dimension": "",
                "plausible_answer_a": "实际月租为1500元",
                "impact_a": "住房成本明确低于预算",
                "plausible_answer_b": "实际月租为2500元",
                "impact_b": "住房成本明确超出预算",
                "reason": "实际月租在预计区间内的不同位置会改变预算判断。",
            }, ensure_ascii=False)
        if "Identify the ONE unknown Reality" in prompt:
            return json.dumps({
                "unknown_fact": "ACTUAL_MONTHLY_RENT",
                "question": self.unknown,
                "why_it_matters": "实际月租会明确住房成本是否落在预算内。",
                "meaning_reference": self.meaning,
                "judgment_reference": self.judgment,
                "grounding": self.grounding(),
            }, ensure_ascii=False)
        if "Choose ONE reliable next action" in prompt:
            return json.dumps({
                "action_type": "PUBLIC_EVIDENCE",
                "action_label": "查询公开租金信息",
                "why_this_action": "实际租金需要可追溯信息确认。",
                "unknown_reference": self.unknown,
            }, ensure_ascii=False)
        if "Form one provisional Current Judgment" in prompt:
            assert "rent range is explicitly an estimate" in prompt
            return json.dumps({
                "judgment": self.judgment,
                "meaning_reference": self.meaning,
                "grounding": self.grounding(),
            }, ensure_ascii=False)
        assert "ESTIMATED_RENT_RANGE is a controlled estimate" in prompt
        return json.dumps({
            "meaning": self.meaning,
            "grounding": self.grounding(),
        }, ensure_ascii=False)


class DecisionReadyRentRangeIntelligence:
    unknown = "这处住所的实际月租是多少？"

    def __init__(self, minimum: int, maximum: int) -> None:
        self.minimum = minimum
        self.maximum = maximum
        self.meaning = (
            f"预计租金为每月{minimum}至{maximum}元，预算为2000元，"
            "实际月租仍待确认。"
        )
        self.judgment = "预计范围可供参考，但实际月租仍会影响预算判断。"

    def grounding(self) -> list[dict[str, str]]:
        return [
            {
                "fact": "ESTIMATED_RENT_RANGE",
                "value": f"{self.minimum}-{self.maximum} CNY/month ESTIMATE",
            },
            {"fact": "BUDGET_REALITY", "value": "2000 CNY/month"},
        ]

    def generate_json(self, prompt: str, **_kwargs) -> str:
        if "Audit whether EVERY claim" in prompt:
            return json.dumps({"supported": True, "unsupported_claims": []})
        if "Judge whether the CURRENT Possible Life" in prompt:
            return json.dumps({
                "status": "DECISION_READY",
                "reason": "预计范围已与预算建立联系。",
                "meaning_reference": self.meaning,
                "judgment_reference": self.judgment,
                "grounding": self.grounding(),
            }, ensure_ascii=False)
        if "Choose ONE reliable next action" in prompt:
            return json.dumps({
                "action_type": "PUBLIC_EVIDENCE",
                "action_label": "查询公开租金信息",
                "why_this_action": "实际租金需要可追溯信息确认。",
                "unknown_reference": self.unknown,
            }, ensure_ascii=False)
        if "Form one provisional Current Judgment" in prompt:
            return json.dumps({
                "judgment": self.judgment,
                "meaning_reference": self.meaning,
                "grounding": self.grounding(),
            }, ensure_ascii=False)
        return json.dumps({
            "meaning": self.meaning,
            "grounding": self.grounding(),
        }, ensure_ascii=False)


class NoBudgetRentRangeIntelligence:
    valid_meaning = "目前只有每月1500至2500元的估算范围，实际租金及其个人意义仍未知。"

    def __init__(self) -> None:
        self.meaning_calls = 0

    @staticmethod
    def grounding() -> list[dict[str, str]]:
        return [
            {"fact": "HOME_IDENTITY", "value": "龙湖时代天街"},
            {
                "fact": "ESTIMATED_RENT_RANGE",
                "value": "1500-2500 CNY/month ESTIMATE",
            },
        ]

    def generate_json(self, prompt: str, **_kwargs) -> str:
        if "Audit whether EVERY claim" in prompt:
            return json.dumps({"supported": True, "unsupported_claims": []})
        self.meaning_calls += 1
        assert "No BUDGET_REALITY is supplied" in prompt
        assert "Interpret only the budget's position relative to that range" not in prompt
        if self.meaning_calls == 1:
            return json.dumps({
                "meaning": "该预算低于估算租金区间下限，住房成本将超出预算。",
                "grounding": self.grounding(),
            }, ensure_ascii=False)
        return json.dumps({
            "meaning": self.valid_meaning,
            "grounding": self.grounding(),
        }, ensure_ascii=False)


def test_estimated_rent_range_requires_budget_reality_for_budget_meaning():
    basis = {
        "HOME_IDENTITY": "龙湖时代天街",
        "ESTIMATED_RENT_RANGE": "1500-2500 CNY/month ESTIMATE",
    }
    intelligence = NoBudgetRentRangeIntelligence()
    service = LivingMeaningService(intelligence=intelligence)

    meaning = service._generate_meaning(basis)

    assert meaning == intelligence.valid_meaning
    assert intelligence.meaning_calls == 2
    assert "预算" not in meaning
    assert LivingMeaningService._validate_interpretation(
        {
            "meaning": "该预算低于估算租金区间下限。",
            "grounding": intelligence.grounding(),
        },
        basis,
        text_field="meaning",
    ) is None


def test_canonical_possible_life_admits_estimate_before_personal_requirements(
    monkeypatch,
):
    conversation_id = uuid_for("canonical-possible-life-rent-estimate")
    client = TestClient(app)
    create_owned_conversation(client, conversation_id)
    home = property_manager.create(conversation_id, Property(
        title="龙湖时代天街",
        geographic_identity="四川省成都市郫都区龙湖·时代天街",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.920730,
        lat=30.753792,
        provenance=PropertyProvenance.USER_PROVIDED,
    ))
    assert home.id

    admitted = _admit_canonical_rent_estimate(conversation_id, home.id)
    assert admitted is not None
    assert admitted.estimated_rent_min == 1500
    assert admitted.estimated_rent_max == 2500
    assert admitted.rent_estimate_kind == "CONTROLLED_ESTIMATE"
    assert admitted.rent is None
    assert admitted.public_rent_evidence is None

    profile_store.save(
        conversation_id,
        LivingProfile(budget=2000, layout_requirement="两室一厅"),
    )
    monkeypatch.setattr(
        living_meaning_service,
        "_intelligence",
        RentRangeIntelligence(),
    )
    result = living_meaning_service.form(conversation_id, home.id)
    assert result.status == "UPDATED"

    interpreted = property_manager.get_scoped(home.id, conversation_id)
    assert interpreted is not None
    assert interpreted.decision_readiness == "NEED_MORE_REALITY"
    assert interpreted.meaningful_unknown == RentRangeIntelligence.unknown
    assert interpreted.reality_action_type == "PUBLIC_EVIDENCE"
    assert "预算" in (interpreted.living_meaning or "")
    assert interpreted.rent is None

    duplicate = _admit_canonical_rent_estimate(conversation_id, home.id)
    assert duplicate is not None
    assert duplicate.living_meaning_reality_hash == interpreted.living_meaning_reality_hash
    assert duplicate.meaningful_unknown_state_hash == interpreted.meaningful_unknown_state_hash


def test_controlled_rent_range_advances_meaning_without_becoming_reality(monkeypatch):
    conversation_id = uuid_for("rent-range-product-loop")
    client = TestClient(app)
    create_owned_conversation(client, conversation_id)
    profile_store.save(conversation_id, LivingProfile(budget=2000))
    home = property_manager.create(conversation_id, Property(
        title="龙湖时代天街",
        geographic_identity="四川省成都市郫都区龙湖·时代天街",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.920730,
        lat=30.753792,
        provenance=PropertyProvenance.USER_PROVIDED,
    ))

    monkeypatch.setattr(
        living_meaning_service,
        "_intelligence",
        RentRangeIntelligence(),
    )
    response = client.post(
        f"/api/properties/{home.id}/controlled-rent-estimate",
        json={
            "conversation_id": conversation_id,
            "minimum_monthly": 1500,
            "maximum_monthly": 2500,
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "UPDATED"
    estimated = property_manager.get_scoped(home.id or "", conversation_id)

    assert estimated is not None
    assert estimated.estimated_rent_min == 1500
    assert estimated.estimated_rent_max == 2500
    assert estimated.rent_estimate_kind == "CONTROLLED_ESTIMATE"
    assert estimated.rent is None
    assert estimated.rent_source is None
    assert estimated.public_rent_evidence is None
    assert estimated.admitted_rent_evidence is None

    basis = LivingMeaningService._basis(estimated, LivingProfile(budget=2000))
    assert basis["ESTIMATED_RENT_RANGE"] == "1500-2500 CNY/month ESTIMATE"
    assert basis["ESTIMATED_RENT_BUDGET_RELATION"] == "BUDGET_WITHIN_ESTIMATED_RANGE"
    assert "RENT_REALITY" not in basis
    assert "EXTERNAL_RENT_OBSERVATION" not in basis

    restored = property_manager.get_scoped(home.id or "", conversation_id)
    assert restored is not None
    assert restored.living_meaning == RentRangeIntelligence.meaning
    assert restored.current_judgment == RentRangeIntelligence.judgment
    assert restored.decision_readiness == "NEED_MORE_REALITY"
    assert restored.meaningful_unknown == RentRangeIntelligence.unknown
    assert restored.rent is None
    assert restored.public_rent_evidence is None
    response = PropertyResponse.model_validate(restored)
    assert response.estimated_rent_min == 1500
    assert response.estimated_rent_max == 2500
    assert response.rent_estimate_kind == "CONTROLLED_ESTIMATE"


@pytest.mark.parametrize(
    ("minimum", "maximum", "relation", "expected_readiness"),
    [
        (2500, 3000, "BUDGET_BELOW_ESTIMATED_RANGE 500 CNY", "DECISION_READY"),
        (1500, 2500, "BUDGET_WITHIN_ESTIMATED_RANGE", "NEED_MORE_REALITY"),
        (500, 1500, "BUDGET_ABOVE_ESTIMATED_RANGE 500 CNY", "DECISION_READY"),
    ],
)
def test_decision_readiness_keeps_actual_rent_unknown_only_when_budget_crosses_estimate(
    monkeypatch,
    minimum,
    maximum,
    relation,
    expected_readiness,
):
    conversation_id = uuid_for(
        f"rent-range-readiness-{minimum}-{maximum}",
    )
    client = TestClient(app)
    create_owned_conversation(client, conversation_id)
    profile_store.save(conversation_id, LivingProfile(budget=2000))
    home = property_manager.create(conversation_id, Property(
        title="龙湖时代天街",
        geographic_identity="四川省成都市郫都区龙湖·时代天街",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.920730,
        lat=30.753792,
        provenance=PropertyProvenance.USER_PROVIDED,
    ))
    intelligence = DecisionReadyRentRangeIntelligence(minimum, maximum)
    monkeypatch.setattr(living_meaning_service, "_intelligence", intelligence)

    response = client.post(
        f"/api/properties/{home.id}/controlled-rent-estimate",
        json={
            "conversation_id": conversation_id,
            "minimum_monthly": minimum,
            "maximum_monthly": maximum,
        },
    )

    assert response.status_code == 200
    estimated = property_manager.get_scoped(home.id or "", conversation_id)
    assert estimated is not None
    assert estimated.rent is None
    assert estimated.rent_source is None
    assert estimated.estimated_rent_min == minimum
    assert estimated.estimated_rent_max == maximum
    basis = LivingMeaningService._basis(estimated, LivingProfile(budget=2000))
    assert basis["ESTIMATED_RENT_BUDGET_RELATION"] == relation
    assert "RENT_REALITY" not in basis
    assert estimated.decision_readiness == expected_readiness

    if expected_readiness == "NEED_MORE_REALITY":
        assert estimated.meaningful_unknown == intelligence.unknown
        assert estimated.reality_action_type == "PUBLIC_EVIDENCE"
    else:
        assert estimated.meaningful_unknown is None


def test_property_restore_refreshes_stale_crossing_range_readiness(monkeypatch):
    conversation_id = uuid_for("rent-range-stale-readiness-projection")
    client = TestClient(app)
    create_owned_conversation(client, conversation_id)
    profile_store.save(conversation_id, LivingProfile(budget=2000))
    home = property_manager.create(conversation_id, Property(
        title="龙湖时代天街",
        geographic_identity="四川省成都市郫都区龙湖·时代天街",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.920730,
        lat=30.753792,
        provenance=PropertyProvenance.USER_PROVIDED,
    ))
    intelligence = DecisionReadyRentRangeIntelligence(1500, 2500)
    monkeypatch.setattr(living_meaning_service, "_intelligence", intelligence)

    response = client.post(
        f"/api/properties/{home.id}/controlled-rent-estimate",
        json={
            "conversation_id": conversation_id,
            "minimum_monthly": 1500,
            "maximum_monthly": 2500,
        },
    )
    assert response.status_code == 200
    current = property_manager.get_scoped(home.id or "", conversation_id)
    assert current is not None and current.current_judgment_state_hash

    stale = property_manager.update_decision_readiness(
        home.id or "",
        conversation_id,
        status="DECISION_READY",
        reason="obsolete readiness",
        state_hash="obsolete-readiness-fingerprint",
        judgment_hash=current.current_judgment_state_hash,
    )
    assert stale is not None and stale.decision_readiness == "DECISION_READY"
    assert stale.meaningful_unknown is None

    restored = client.get(f"/api/properties?conversation_id={conversation_id}")
    assert restored.status_code == 200
    projected = next(item for item in restored.json()["items"] if item["id"] == home.id)
    assert projected["decision_readiness"] == "NEED_MORE_REALITY"
    assert projected["meaningful_unknown"] == intelligence.unknown
    assert projected["reality_action_type"] == "PUBLIC_EVIDENCE"
    assert projected["rent"] is None

    persisted = property_manager.get_scoped(home.id or "", conversation_id)
    assert persisted is not None
    assert persisted.decision_readiness == "NEED_MORE_REALITY"
    assert persisted.meaningful_unknown == intelligence.unknown
