import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from app.core.ai_client import AIClient
from app.main import app
from app.models.profile import LivingProfile
from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
    PropertyRentSource,
)
from app.services.external_rent_reality_service import (
    USER_INITIATED_RENT_ACTION_LABEL,
    USER_INITIATED_RENT_ACTION_WHY,
    ExternalRentRealityService,
)
from app.services.living_meaning_service import LivingMeaningService
from app.services.property_manager import property_manager
from app.services.public_rental_evidence import PublicRentalEvidence
from app.stores.runtime import profile_store
from fastapi.testclient import TestClient
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


class FakePublicSearch:
    evidence = PublicRentalEvidence(
        source_reference="https://rent.example/listing/123",
        source_title="中关村东大院整租",
        source_provider="rent.example",
        property_text="北京市海淀区中关村东大院 当前整租 6800 元/月",
        observed_at="2026-09-20T10:00:00+00:00",
        published_at="2026-09-20T09:00:00+00:00",
        grounded_property_identity="北京市海淀区中关村东大院",
    )

    def search(self, **_kwargs):
        return [self.evidence]

    def as_tool_result(self, evidence):
        return json.dumps({"evidence": [item.__dict__ for item in evidence]}, ensure_ascii=False)


class FakeCompletions:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            function = SimpleNamespace(
                name="search_public_rental_evidence",
                arguments=json.dumps({
                    "property_name": "中关村东大院",
                    "city": "北京市",
                    "district": "北京市海淀区中关村东大院",
                    "lng": 116.32,
                    "lat": 39.98,
                }),
            )
            message = SimpleNamespace(
                content=None,
                tool_calls=[SimpleNamespace(id="call-1", function=function)],
            )
        elif len(self.calls) == 2:
            tool_result = json.loads(kwargs["messages"][-1]["content"])
            evidence = tool_result["evidence"][0]
            message = SimpleNamespace(
                content=json.dumps({
                    "rent_monthly": 6800,
                    "identity_status": "GROUNDED",
                    "source_reference": evidence["source_reference"],
                    "observed_at": evidence["observed_at"],
                    "evidence_excerpt": "北京市海淀区中关村东大院 当前整租 6800 元/月",
                }),
                tool_calls=None,
            )
        else:
            message = SimpleNamespace(
                content=json.dumps({
                    "claim_type": "SINGLE_OBSERVATION",
                    "rent_monthly": 6800,
                    "source_reference": "https://rent.example/listing/123",
                    "observed_at": "2026-09-20T10:00:00+00:00",
                    "evidence_excerpt": "北京市海淀区中关村东大院 当前整租 6800 元/月",
                }, ensure_ascii=False),
                tool_calls=None,
            )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeOpenAI:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions())

    def with_options(self, **_kwargs):
        return self


class FakeEvidenceMeaning:
    def __init__(self):
        self.calls = []

    def form(self, conversation_id, property_id):
        self.calls.append((conversation_id, property_id))
        current = property_manager.get_scoped(property_id, conversation_id)
        assert current is not None
        assert current.public_rent_evidence is not None
        assert current.public_rent_evidence["understanding"]["claim_type"] == "SINGLE_OBSERVATION"
        updated = property_manager.update_living_meaning(
            property_id,
            conversation_id,
            meaning="当前发现的租赁可能低于预算，但整体租金水平仍未知。",
            reality_hash="external-evidence-meaning",
        )
        return SimpleNamespace(property=updated)


def test_model_tool_evidence_becomes_guarded_external_rent_reality():
    client = TestClient(app)
    conversation_id = uuid_for("external-rent-reality")
    create_owned_conversation(client, conversation_id)
    target = property_manager.create(conversation_id, Property(
        title="中关村东大院",
        district="北京市",
        geographic_identity="北京市海淀区中关村东大院",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.32,
        lat=39.98,
        provenance=PropertyProvenance.AMAP_RESIDENTIAL_POI,
        external_id="amap-home-1",
    ))
    intelligence = AIClient()
    fake_openai = FakeOpenAI()
    intelligence.client = fake_openai
    class FakeMeaning:
        def __init__(self):
            self.calls = []

        def form(self, cid, pid):
            self.calls.append((cid, pid))
            refreshed = property_manager.update_living_meaning(
                pid, cid, meaning="租金已从来源证据确认。", reality_hash="external-rent",
            )
            return SimpleNamespace(property=refreshed)

    meanings = FakeMeaning()
    service = ExternalRentRealityService(
        intelligence=intelligence,
        evidence_search=FakePublicSearch(),
        meanings=meanings,
    )

    result = service.acquire(conversation_id, target.id or "")

    assert result.status == "UPDATED"
    stored = property_manager.get_scoped(target.id or "", conversation_id)
    assert stored is not None
    assert stored.rent == 6800
    assert stored.rent_source == PropertyRentSource.EXTERNAL_SOURCE
    assert stored.rent_source_reference == "https://rent.example/listing/123"
    assert stored.rent_observed_at == "2026-09-20T10:00:00+00:00"
    assert stored.admitted_rent_evidence is not None
    assert stored.admitted_rent_evidence["source_reference"] == stored.rent_source_reference
    assert stored.admitted_rent_evidence["observed_at"] == stored.rent_observed_at
    assert stored.admitted_rent_evidence["published_at"] == "2026-09-20T09:00:00+00:00"
    assert stored.admitted_rent_evidence["admission"]["property_id"] == target.id
    assert stored.admitted_rent_evidence["admission"]["rent_monthly"] == 6800
    assert client.get(f"/api/properties?conversation_id={conversation_id}").json()["items"][0]["admitted_rent_evidence"] == stored.admitted_rent_evidence
    assert meanings.calls == [(conversation_id, target.id)]
    assert stored.living_meaning == "租金已从来源证据确认。"
    assert result.property is not None
    assert result.property.living_meaning == stored.living_meaning
    calls = fake_openai.chat.completions.calls
    assert calls[0]["tools"][0]["function"]["name"] == "search_public_rental_evidence"
    assert calls[1]["messages"][-1]["role"] == "tool"
    replaced = property_manager.update_confirmed_rent(
        target.id or "", conversation_id, 6900, PropertyRentSource.USER_PROVIDED,
    )
    assert replaced is not None
    assert replaced.admitted_rent_evidence is None
    assert replaced.rent_source_reference is None
    assert replaced.rent_observed_at is None


@pytest.mark.parametrize(
    ("changes", "evidence_changes"),
    [
        ({"identity_status": "UNRESOLVED"}, {}),
        ({"evidence_excerpt": "另一小区 当前整租 6800 元/月"},
         {"property_text": "另一小区 当前整租 6800 元/月"}),
        ({"evidence_excerpt": "中关村东大院 当前整租 6800 元/月"},
         {"property_text": "中关村东大院 当前整租 6800 元/月"}),
        ({"rent_monthly": 7000}, {}),
        ({"evidence_excerpt": "北京市海淀区中关村东大院 当前整租 7000 元/月"},
         {"property_text": "北京市海淀区中关村东大院 当前整租 7000 元/月"}),
        ({"observed_at": "2026-09-20T10:01:00+00:00"}, {}),
        ({"observed_at": "not-a-time"}, {"observed_at": "not-a-time"}),
        ({"observed_at": "2026-09-20T10:00:00"},
         {"observed_at": "2026-09-20T10:00:00"}),
    ],
)
def test_external_rent_rejects_unbound_identity_amount_or_time(changes, evidence_changes):
    target = Property(
        title="中关村东大院",
        geographic_identity="北京市海淀区中关村东大院",
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.32, lat=39.98,
    )
    evidence = replace(FakePublicSearch.evidence, **evidence_changes)
    interpretation = {
        "rent_monthly": 6800,
        "identity_status": "GROUNDED",
        "source_reference": evidence.source_reference,
        "observed_at": evidence.observed_at,
        "evidence_excerpt": evidence.property_text,
        **changes,
    }
    assert ExternalRentRealityService._admit(interpretation, [evidence], target) is None


def test_public_evidence_action_stops_before_reality_admission():
    client = TestClient(app)
    conversation_id = uuid_for("public-evidence-action")
    create_owned_conversation(client, conversation_id)
    target = property_manager.create(conversation_id, Property(
        title="中关村东大院",
        geographic_identity="北京市海淀区中关村东大院",
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.32,
        lat=39.98,
        meaningful_unknown="中关村东大院的月租金是多少？",
        meaningful_unknown_why="租金会改变当前预算权衡。",
        reality_action_type="PUBLIC_EVIDENCE",
        reality_action_label="查询公开租金挂牌信息",
        reality_action_why="公开挂牌可提供来源",
        reality_action_state_hash="action-state-1",
    ))
    intelligence = AIClient()
    fake_openai = FakeOpenAI()
    intelligence.client = fake_openai
    meanings = FakeEvidenceMeaning()
    service = ExternalRentRealityService(
        intelligence=intelligence, evidence_search=FakePublicSearch(),
        meanings=meanings,
    )

    before = property_manager.get_scoped(target.id or "", conversation_id)
    assert before is not None and before.public_rent_evidence is None
    result = service.execute_public_evidence_action(conversation_id, target.id or "")
    assert result.status == "EVIDENCE_READY"
    stored = property_manager.get_scoped(target.id or "", conversation_id)
    assert stored is not None and stored.public_rent_evidence is not None
    assert stored.public_rent_evidence["source_reference"] == "https://rent.example/listing/123"
    assert stored.public_rent_evidence["observed_at"] == "2026-09-20T10:00:00+00:00"
    assert stored.public_rent_evidence["grounded_property_identity"] == target.geographic_identity
    assert stored.public_rent_evidence["understanding"] == {
        "claim_type": "SINGLE_OBSERVATION",
        "rent_monthly": 6800,
        "understanding": "当前发现一种约 ¥6,800/月的真实租赁可能。",
        "source_reference": "https://rent.example/listing/123",
        "observed_at": "2026-09-20T10:00:00+00:00",
        "evidence_excerpt": "北京市海淀区中关村东大院 当前整租 6800 元/月",
    }
    assert stored.rent is None and stored.rent_source is None
    assert stored.living_meaning == "当前发现的租赁可能低于预算，但整体租金水平仍未知。"
    assert meanings.calls == [(conversation_id, target.id)]
    assert fake_openai.chat.completions.calls[0]["tools"][0]["function"]["name"] == "search_public_rental_evidence"


def test_public_evidence_action_rejects_same_name_without_grounded_identity():
    class SameNameOnlySearch(FakePublicSearch):
        evidence = replace(
            FakePublicSearch.evidence,
            property_text="中关村东大院 当前整租 6800 元/月",
            grounded_property_identity=None,
        )

    client = TestClient(app)
    conversation_id = uuid_for("same-name-public-evidence")
    create_owned_conversation(client, conversation_id)
    profile_store.save(conversation_id, LivingProfile(layout_requirement="两室一厅"))
    target = property_manager.create(conversation_id, Property(
        title="中关村东大院",
        geographic_identity="北京市海淀区中关村东大院",
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.32,
        lat=39.98,
        meaningful_unknown="中关村东大院的月租金是多少？",
        meaningful_unknown_why="租金会改变当前预算权衡。",
        reality_action_type="PUBLIC_EVIDENCE",
        reality_action_label="查询公开租金挂牌信息",
        reality_action_why="公开挂牌可提供来源",
        reality_action_state_hash="same-name-action",
        living_meaning="户型要求与实际情况仍需核对。",
        current_judgment="租金仍未知。",
    ))

    class NoEvidenceIntelligence:
        def generate_json_with_public_evidence_tool(self, _prompt, *, dispatch, **_kwargs):
            dispatch({"property_name": "中关村东大院"})
            return '{"done":true}'

        def generate_json(self, _prompt, **_kwargs):
            return json.dumps({
                "next_move_type": "SHIFT_ATTENTION",
                "next_move_label": "保留租金未知，转向其他现实",
                "why_this_move": "本次没有取得可绑定当前住所的证据。",
                "unknown_reference": "中关村东大院的月租金是多少？",
                "action_reference": "查询公开租金挂牌信息",
                "outcome_reference": "NO_EVIDENCE",
            }, ensure_ascii=False)

    intelligence = NoEvidenceIntelligence()
    service = ExternalRentRealityService(
        intelligence=intelligence, evidence_search=SameNameOnlySearch(),
    )

    result = service.execute_public_evidence_action(conversation_id, target.id or "")

    assert result.status == "NO_EVIDENCE"
    stored = property_manager.get_scoped(target.id or "", conversation_id)
    assert stored is not None
    assert stored.public_rent_evidence is None
    assert stored.rent is None and stored.rent_source is None
    assert stored.meaningful_unknown == target.meaningful_unknown


def test_user_initiated_public_evidence_action_executes_without_unknown():
    client = TestClient(app)
    conversation_id = uuid_for("user-initiated-public-evidence")
    create_owned_conversation(client, conversation_id)
    target = property_manager.create(conversation_id, Property(
        title="中关村东大院",
        geographic_identity="北京市海淀区中关村东大院",
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.32, lat=39.98,
        reality_action_type="PUBLIC_EVIDENCE",
        reality_action_label=USER_INITIATED_RENT_ACTION_LABEL,
        reality_action_why=USER_INITIATED_RENT_ACTION_WHY,
        reality_action_state_hash="user-rent-action-hash",
    ))
    intelligence = AIClient()
    fake_openai = FakeOpenAI()
    intelligence.client = fake_openai
    meanings = FakeEvidenceMeaning()
    service = ExternalRentRealityService(
        intelligence=intelligence, evidence_search=FakePublicSearch(),
        meanings=meanings,
    )

    result = service.execute_public_evidence_action(conversation_id, target.id or "")

    assert result.status == "EVIDENCE_READY"
    stored = property_manager.get_scoped(target.id or "", conversation_id)
    assert stored is not None
    assert stored.meaningful_unknown is None
    assert stored.rent is None and stored.rent_source is None
    assert stored.public_rent_evidence is not None
    assert stored.public_rent_evidence["source_reference"] == "https://rent.example/listing/123"
    assert stored.public_rent_evidence["observed_at"] == "2026-09-20T10:00:00+00:00"
    assert stored.public_rent_evidence["understanding"]["claim_type"] == "SINGLE_OBSERVATION"
    assert meanings.calls == [(conversation_id, target.id)]
    assert fake_openai.chat.completions.calls[0]["tools"][0]["function"]["name"] == "search_public_rental_evidence"

    stale = property_manager.create(conversation_id, Property(
        title="另一处住所", geographic_status=GeographicStatus.GROUNDED,
        lng=116.321, lat=39.981,
        reality_action_type="PUBLIC_EVIDENCE",
        reality_action_label=USER_INITIATED_RENT_ACTION_LABEL,
        reality_action_why=USER_INITIATED_RENT_ACTION_WHY,
    ))
    mismatched = property_manager.create(conversation_id, Property(
        title="第三处住所", geographic_status=GeographicStatus.GROUNDED,
        lng=116.322, lat=39.982,
        reality_action_type="PUBLIC_EVIDENCE",
        reality_action_label="查询公开租金信息",
        reality_action_why=USER_INITIATED_RENT_ACTION_WHY,
        reality_action_state_hash="mismatched-action-hash",
    ))
    assert service.execute_public_evidence_action(conversation_id, stale.id or "").status == "NOT_AVAILABLE"
    assert service.execute_public_evidence_action(conversation_id, mismatched.id or "").status == "NOT_AVAILABLE"


def test_unsupported_public_evidence_understanding_preserves_unknown():
    class RangeIntelligence:
        def generate_json_with_public_evidence_tool(self, _prompt, *, dispatch, **_kwargs):
            dispatch({"property_name": "中关村东大院"})
            return '{"done":true}'

        def generate_json(self, _prompt, **_kwargs):
            return json.dumps({
                "claim_type": "RANGE",
                "rent_monthly": 6800,
                "source_reference": "https://rent.example/listing/123",
                "observed_at": "2026-09-20T10:00:00+00:00",
                "evidence_excerpt": "北京市海淀区中关村东大院 当前整租 6800 元/月",
            }, ensure_ascii=False)

    client = TestClient(app)
    conversation_id = uuid_for("unsupported-evidence-understanding")
    create_owned_conversation(client, conversation_id)
    target = property_manager.create(conversation_id, Property(
        title="中关村东大院",
        geographic_identity="北京市海淀区中关村东大院",
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.32,
        lat=39.98,
        meaningful_unknown="中关村东大院的租住成本大致是多少？",
        meaningful_unknown_why="租住成本可能改变预算判断。",
        reality_action_type="PUBLIC_EVIDENCE",
        reality_action_label="查询公开租金挂牌信息",
        reality_action_why="公开挂牌可提供来源",
        reality_action_state_hash="unsupported-understanding-action",
    ))
    meanings = FakeEvidenceMeaning()
    service = ExternalRentRealityService(
        intelligence=RangeIntelligence(),
        evidence_search=FakePublicSearch(),
        meanings=meanings,
    )

    result = service.execute_public_evidence_action(conversation_id, target.id or "")

    assert result.status == "EVIDENCE_READY"
    stored = property_manager.get_scoped(target.id or "", conversation_id)
    assert stored is not None and stored.public_rent_evidence is not None
    assert "understanding" not in stored.public_rent_evidence
    assert stored.rent is None and stored.rent_source is None
    assert stored.meaningful_unknown == target.meaningful_unknown
    assert meanings.calls == []


def test_single_observation_can_form_budget_bounded_personal_meaning():
    home = Property(
        title="龙湖时代天街",
        geographic_status=GeographicStatus.GROUNDED,
        public_rent_evidence={
            "understanding": {
                "claim_type": "SINGLE_OBSERVATION",
                "rent_monthly": 1500,
                "understanding": "当前发现一种约 ¥1,500/月的真实租赁可能。",
            },
        },
    )
    basis = LivingMeaningService._basis(home, LivingProfile(budget=2000))

    class MeaningIntelligence:
        def generate_json(self, prompt, **_kwargs):
            if "Audit whether EVERY claim" in prompt:
                return json.dumps({
                    "supported": True,
                    "unsupported_claims": [],
                }, ensure_ascii=False)
            return json.dumps({
                "meaning": "当前发现的一种租赁可能比预算低500元，但整体租金水平仍未知。",
                "grounding": [
                    {
                        "fact": "EXTERNAL_RENT_OBSERVATION",
                        "value": "当前发现一种约 ¥1,500/月的真实租赁可能。",
                    },
                    {"fact": "BUDGET_REALITY", "value": "2000 CNY/month"},
                    {
                        "fact": "EXTERNAL_RENT_BUDGET_RELATION",
                        "value": "OBSERVED_OPTION_UNDER_BUDGET 500 CNY",
                    },
                ],
            }, ensure_ascii=False)

    meaning = LivingMeaningService(
        intelligence=MeaningIntelligence(),
    )._generate_meaning(basis)

    assert "RENT_REALITY" not in basis
    assert basis["EXTERNAL_RENT_BUDGET_RELATION"] == (
        "OBSERVED_OPTION_UNDER_BUDGET 500 CNY"
    )
    assert meaning == "当前发现的一种租赁可能比预算低500元，但整体租金水平仍未知。"


def test_no_evidence_feedback_persists_one_next_move_without_changing_reality():
    class EmptySearch(FakePublicSearch):
        def search(self, **_kwargs):
            return []

    class FeedbackIntelligence:
        move_type = "UNSUPPORTED"
        tool_called = False

        def generate_json_with_public_evidence_tool(self, _prompt, *, dispatch, **_kwargs):
            self.tool_called = True
            dispatch({"property_name": "中关村东大院"})
            return '{"done":true}'

        def generate_json(self, _prompt, **_kwargs):
            return json.dumps({
                "next_move_type": self.move_type,
                "next_move_label": "如果已看到挂牌，可提供实际月租",
                "why_this_move": "本次未取得可追溯证据，直接信息可能补足未知。",
                "unknown_reference": "中关村东大院的月租金是多少？",
                "action_reference": "查询公开租金挂牌信息",
                "outcome_reference": "NO_EVIDENCE",
            }, ensure_ascii=False)

    client = TestClient(app)
    conversation_id = uuid_for("public-action-feedback")
    create_owned_conversation(client, conversation_id)
    profile_store.save(conversation_id, LivingProfile(
        work_location="融科资讯中心", budget=6000,
        geographic_identity="北京市海淀区融科资讯中心",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.3205, lat=39.9839,
    ))
    target = property_manager.create(conversation_id, Property(
        title="中关村东大院",
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.32, lat=39.98,
        commute_minutes=1,
        commute_mode=CommuteMode.WALKING,
        grocery_external_id="grocery-1", grocery_walking_minutes=7,
        living_meaning="步行便利但有预算压力。",
        current_judgment="以成本换取便利。",
        meaningful_unknown="中关村东大院的月租金是多少？",
        meaningful_unknown_why="租金影响预算权衡。",
        meaningful_unknown_state_hash="unknown-state-1",
        reality_action_type="PUBLIC_EVIDENCE",
        reality_action_label="查询公开租金挂牌信息",
        reality_action_why="公开来源可查",
        reality_action_state_hash="action-state-1",
    ))
    intelligence = FeedbackIntelligence()
    service = ExternalRentRealityService(
        intelligence=intelligence, evidence_search=EmptySearch(),
    )
    before = property_manager.get_scoped(target.id or "", conversation_id)
    assert before is not None
    assert before.reality_action_type == "PUBLIC_EVIDENCE"
    assert before.reality_action_state_hash == "action-state-1"
    assert before.public_rent_evidence is None
    assert before.meaningful_unknown
    assert before.rent is None
    assert before.title
    assert before.geographic_status == GeographicStatus.GROUNDED
    assert before.lng is not None and before.lat is not None

    rejected = service.execute_public_evidence_action(conversation_id, target.id or "")
    assert intelligence.tool_called
    assert rejected.status == "NO_EVIDENCE"
    partial = property_manager.get_scoped(target.id or "", conversation_id)
    assert partial is not None and partial.public_action_outcome == "NO_EVIDENCE"
    assert partial.feedback_move_type is None

    intelligence.move_type = "USER_REALITY"
    accepted = service.feedback_from_no_evidence(conversation_id, target.id or "")
    assert accepted.status == "NO_EVIDENCE"
    stored = property_manager.get_scoped(target.id or "", conversation_id)
    assert stored is not None
    assert stored.feedback_move_type == "USER_REALITY"
    assert stored.feedback_move_label == "如果已看到挂牌，可提供实际月租"
    assert stored.rent is None and stored.public_rent_evidence is None
    assert stored.meaningful_unknown == target.meaningful_unknown
    assert stored.living_meaning == target.living_meaning
    assert stored.current_judgment == target.current_judgment

    changed = property_manager.update_reality_action(
        target.id or "", conversation_id,
        action_type="USER_REALITY", label="直接观察",
        why="方式改变", state_hash="action-state-2",
    )
    assert changed is not None
    assert changed.public_action_outcome is None
    assert changed.feedback_move_type is None

    restored_action = property_manager.update_reality_action(
        target.id or "", conversation_id,
        action_type="PUBLIC_EVIDENCE", label="查询公开租金挂牌信息",
        why="公开来源可查", state_hash="action-state-3",
    )
    assert restored_action is not None
    property_manager.record_public_action_no_evidence(
        target.id or "", conversation_id, action_hash="action-state-3",
    )
    service.feedback_from_no_evidence(conversation_id, target.id or "")
    changed_unknown = property_manager.update_meaningful_unknown(
        target.id or "", conversation_id,
        question="另一项尚未确认的现实是什么？",
        why="需要重新判断。", state_hash="unknown-state-2",
    )
    assert changed_unknown is not None
    assert changed_unknown.public_action_outcome is None
    assert changed_unknown.feedback_move_type is None
