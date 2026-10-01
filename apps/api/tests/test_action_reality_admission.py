import json
from dataclasses import replace

import pytest

from app.models.conversation import ConversationMessage
from app.models.property import GeographicStatus, Property
from app.models.reality_need import RealityNeedResolutionMode
from app.services.chat_service import chat_service
from app.services.possible_life_reality_action import PossibleLifeRealityActionService
from app.services.property_manager import property_manager
from app.services.user_reality_return import UserRealityReturn, user_reality_return
from app.stores.runtime import (
    possible_life_meaningful_unknown_store,
    possible_life_reality_action_store,
    possible_life_store,
    reality_need_store,
)
from tests.ids import uuid_for
from tests.test_possible_life_reality_action import ActionIntelligence, setup_need

EXPRESSION = "我确认了，这套是两室一厅。"


class LayoutIntelligence:
    def __init__(self, *, property_id: str, returned_type: str = "LAYOUT") -> None:
        self.property_id = property_id
        self.returned_type = returned_type

    def generate_json(self, prompt: str, **_kwargs) -> str:
        if "Determine whether the CURRENT user message explicitly states" in prompt:
            return json.dumps({
                "unknown_reference": None,
                "reality_type": self.returned_type,
                "value": "两室一厅" if self.returned_type == "LAYOUT" else None,
            }, ensure_ascii=False)
        return json.dumps({
            "claim_nature": "PROPERTY_REALITY",
            "layout_requirement": None,
            "reality_type": "LAYOUT",
            "claim_quote": EXPRESSION,
            "property_id": self.property_id,
            "binding_evidence": None,
            "binding_source": "FOCUS",
            "attention_property_id": None,
            "attention_evidence": None,
        }, ensure_ascii=False)


def bound_layout_return(cid: str):
    residence, _, possible_life, _, unknown, need = setup_need(
        cid, RealityNeedResolutionMode.REAL_WORLD_CONTACT,
    )
    action = PossibleLifeRealityActionService(
        intelligence=ActionIntelligence("USER_REALITY"),
    ).form(cid, need)
    assert action is not None
    service = UserRealityReturn(intelligence=LayoutIntelligence(
        property_id=residence.id or "",
    ))
    resolution = service.resolve_expression(
        [ConversationMessage("user", EXPRESSION)], property_manager.list(cid),
        EXPRESSION, focused_property_id=residence.id, conversation_id=cid,
    )
    assert resolution.action_reality_return is not None
    return residence, possible_life, unknown, need, action, service, resolution


def test_bound_user_reality_admits_only_possible_life_residence_layout() -> None:
    cid = uuid_for("bound-action-layout-admission")
    residence, possible_life, unknown, need, action, service, resolution = (
        bound_layout_return(cid)
    )
    other = property_manager.create(cid, Property(
        title="另一处住所", geographic_status=GeographicStatus.GROUNDED,
        geographic_identity="北京市海淀区另一处住所", lng=116.3, lat=39.9,
    ))
    before = (
        possible_life_store.get(cid, possible_life.id),
        reality_need_store.get(cid, unknown.id),
        possible_life_reality_action_store.get(cid, need.id),
    )
    admitted = service.admit(
        cid, residence.id or "", EXPRESSION,
        expected_reality_type=resolution.reality_type,
        action_reality_return=resolution.action_reality_return,
    )
    assert admitted is not None
    assert admitted.id == possible_life.residence_property_id == residence.id
    assert admitted.layout_expression == "两室一厅"
    assert admitted.layout_source == "USER_PROVIDED"
    assert property_manager.get_scoped(other.id or "", cid).layout_expression is None
    assert possible_life_meaningful_unknown_store.get(cid, possible_life.id) is None
    resolved = possible_life_meaningful_unknown_store.get_by_id(cid, unknown.id)
    assert resolved is not None
    assert resolved.id == unknown.id
    assert resolved.possible_life_id == possible_life.id
    assert resolved.question == unknown.question
    assert resolved.resolved_at is not None
    assert resolved.resolved_property_id == residence.id
    assert resolved.resolved_layout_expression == "两室一厅"
    assert resolved.resolved_reality_source == "USER_PROVIDED"
    assert before == (
        possible_life_store.get(cid, possible_life.id),
        reality_need_store.get(cid, unknown.id),
        possible_life_reality_action_store.get(cid, need.id),
    )
    assert resolution.action_reality_return.action_id == action.id


@pytest.mark.parametrize(
    "field", ["action_id", "reality_need_id", "possible_life_id",
              "residence_property_id"],
)
def test_mismatched_authoritative_binding_cannot_admit(field: str) -> None:
    cid = uuid_for(f"bound-action-layout-mismatch-{field}")
    residence, possible_life, unknown, _, _, service, resolution = bound_layout_return(cid)
    forged = replace(
        resolution.action_reality_return,
        **{field: uuid_for(f"different-{field}")},
    )
    assert service.admit(
        cid, residence.id or "", EXPRESSION,
        expected_reality_type="LAYOUT", action_reality_return=forged,
    ) is None
    assert property_manager.get_scoped(residence.id or "", cid).layout_expression is None
    assert possible_life_meaningful_unknown_store.get(cid, possible_life.id) == unknown


def test_unrelated_or_ambiguous_return_does_not_admit() -> None:
    cid = uuid_for("bound-action-layout-unrelated")
    residence, possible_life, unknown, _, _, service, resolution = bound_layout_return(cid)
    binding = resolution.action_reality_return
    assert service.admit(
        cid, residence.id or "", "另一处住所实际是两室一厅。",
        expected_reality_type="LAYOUT", action_reality_return=binding,
    ) is None
    ambiguous = UserRealityReturn(intelligence=LayoutIntelligence(
        property_id=residence.id or "", returned_type="NONE",
    ))
    assert ambiguous.admit(
        cid, residence.id or "", EXPRESSION,
        expected_reality_type="LAYOUT", action_reality_return=binding,
    ) is None
    assert property_manager.get_scoped(residence.id or "", cid).layout_expression is None
    assert possible_life_meaningful_unknown_store.get(cid, possible_life.id) == unknown


def test_property_reality_without_action_binding_does_not_resolve_unknown() -> None:
    cid = uuid_for("layout-without-action-binding")
    residence, possible_life, unknown, _, _, service, _ = bound_layout_return(cid)
    admitted = service.admit(
        cid, residence.id or "", EXPRESSION, expected_reality_type="LAYOUT",
    )
    assert admitted is not None
    assert admitted.layout_expression == "两室一厅"
    assert possible_life_meaningful_unknown_store.get(cid, possible_life.id) == unknown


def test_failed_property_admission_does_not_resolve_unknown(monkeypatch) -> None:
    cid = uuid_for("failed-layout-admission-keeps-unknown")
    residence, possible_life, unknown, _, _, service, resolution = bound_layout_return(cid)
    monkeypatch.setattr(
        service._properties, "admit_user_layout_reality",
        lambda *_args, **_kwargs: None,
    )
    assert service.admit(
        cid, residence.id or "", EXPRESSION, expected_reality_type="LAYOUT",
        action_reality_return=resolution.action_reality_return,
    ) is None
    assert possible_life_meaningful_unknown_store.get(cid, possible_life.id) == unknown


def test_resolving_one_possible_life_leaves_another_unknown_unchanged() -> None:
    cid = uuid_for("resolve-one-possible-life")
    other_cid = uuid_for("resolve-other-possible-life")
    residence, _, _, _, _, service, resolution = bound_layout_return(cid)
    other_residence, other_life, other_unknown, _, _, _, _ = bound_layout_return(
        other_cid,
    )
    assert service.admit(
        cid, residence.id or "", EXPRESSION, expected_reality_type="LAYOUT",
        action_reality_return=resolution.action_reality_return,
    ) is not None
    assert possible_life_meaningful_unknown_store.get(
        other_cid, other_life.id,
    ) == other_unknown
    assert property_manager.get_scoped(
        other_residence.id or "", other_cid,
    ).layout_expression is None


def test_resolved_unknown_keeps_identity_when_later_unknown_is_admitted() -> None:
    cid = uuid_for("resolved-layout-unknown-history")
    residence, possible_life, unknown, _, _, service, resolution = bound_layout_return(cid)
    assert service.admit(
        cid, residence.id or "", EXPRESSION, expected_reality_type="LAYOUT",
        action_reality_return=resolution.action_reality_return,
    ) is not None
    later = possible_life_meaningful_unknown_store.save(
        cid, replace(
            unknown, id=uuid_for("later-unknown-after-layout"),
            question="这套住所夜间室内是否安静？", state_hash="later-state",
        ),
    )
    assert later.id != unknown.id
    assert possible_life_meaningful_unknown_store.get(cid, possible_life.id) == later
    resolved = possible_life_meaningful_unknown_store.get_by_id(cid, unknown.id)
    assert resolved is not None and resolved.resolved_at is not None
    assert resolved.question == unknown.question


def test_chat_path_passes_bound_context_to_existing_admission(monkeypatch) -> None:
    cid = uuid_for("bound-action-layout-chat-path")
    residence, _, _, _, _, _, resolution = bound_layout_return(cid)
    received = []
    monkeypatch.setattr(
        user_reality_return, "resolve_expression", lambda *_args, **_kwargs: resolution,
    )
    def capture(_cid, _property_id, _message, **kwargs):
        received.append((_cid, _property_id, _message, kwargs))
        return residence
    monkeypatch.setattr(user_reality_return, "admit", capture)
    chat_service.chat_stream(
        conversation_id=cid, message=EXPRESSION,
        user_reality_property_id=residence.id,
    )
    assert received == [(cid, residence.id, EXPRESSION, {
        "expected_reality_type": "LAYOUT",
        "action_reality_return": resolution.action_reality_return,
    })]
