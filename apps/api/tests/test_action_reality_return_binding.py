import json
from dataclasses import replace

import pytest
from app.models.conversation import ConversationMessage
from app.models.possible_life_reality_action import PossibleLifeRealityActionType
from app.models.reality_need import RealityNeedResolutionMode
from app.services.possible_life_reality_action import PossibleLifeRealityActionService
from app.services.property_manager import property_manager
from app.services.user_reality_return import UserRealityReturn
from app.stores.runtime import possible_life_reality_action_store
from tests.ids import uuid_for
from tests.test_possible_life_reality_action import ActionIntelligence, setup_need


class ExpressionIntelligence:
    def __init__(self, *, property_id: str, title: str, claim: str = "两室一厅") -> None:
        self.property_id = property_id
        self.title = title
        self.claim = claim

    def generate_json(self, prompt: str, **_kwargs) -> str:
        if "Determine whether the CURRENT user message explicitly states" in prompt:
            return json.dumps({
                "unknown_reference": None,
                "reality_type": "LAYOUT",
                "value": self.claim,
            }, ensure_ascii=False)
        return json.dumps({
            "claim_nature": "PROPERTY_REALITY",
            "layout_requirement": None,
            "reality_type": "LAYOUT",
            "claim_quote": self.claim,
            "property_id": self.property_id,
            "binding_evidence": self.title,
            "binding_source": "USER_EXPRESSION",
            "attention_property_id": None,
            "attention_evidence": None,
        }, ensure_ascii=False)


class TerseAnswerIntelligence:
    def generate_json(self, _prompt: str, **_kwargs) -> str:
        return json.dumps({
            "claim_nature": "PERSONAL_REQUIREMENT",
            "layout_requirement": "两室一厅",
            "reality_type": None,
            "claim_quote": None,
            "property_id": None,
            "binding_evidence": None,
            "binding_source": None,
            "attention_property_id": None,
            "attention_evidence": None,
        }, ensure_ascii=False)


def test_focused_terse_return_binds_only_active_user_reality_action() -> None:
    cid = uuid_for("action-return-focused-terse")
    residence, _, possible_life, _, _, need = setup_need(
        cid, RealityNeedResolutionMode.REAL_WORLD_CONTACT,
    )
    action = PossibleLifeRealityActionService(
        intelligence=ActionIntelligence("USER_REALITY"),
    ).form(cid, need)
    assert action is not None
    service = UserRealityReturn(intelligence=TerseAnswerIntelligence())
    result = service.resolve_expression(
        [ConversationMessage("user", "两室一厅")], property_manager.list(cid),
        "两室一厅", focused_property_id=residence.id, conversation_id=cid,
    )
    assert result.property_id == residence.id
    assert result.reality_type == "LAYOUT"
    assert result.action_reality_return is not None
    assert result.action_reality_return.action_id == action.id
    assert result.action_reality_return.reality_need_id == need.id
    assert result.action_reality_return.possible_life_id == possible_life.id
    assert property_manager.get_scoped(residence.id or "", cid).layout_expression is None


@pytest.mark.parametrize("action_type", ["USER_REALITY", "PUBLIC_EVIDENCE"])
def test_only_matching_user_reality_action_binds_factual_return(
    action_type: str,
) -> None:
    cid = uuid_for(f"action-return-{action_type}")
    residence, _, possible_life, _, _, need = setup_need(
        cid, RealityNeedResolutionMode.REAL_WORLD_CONTACT,
    )
    action = PossibleLifeRealityActionService(
        intelligence=ActionIntelligence(action_type),
    ).form(cid, need)
    assert action is not None
    title = residence.title or ""
    service = UserRealityReturn(intelligence=ExpressionIntelligence(
        property_id=residence.id or "", title=title,
    ))
    message = f"{title}这套房实际是两室一厅"
    resolution = service.resolve_expression(
        [ConversationMessage("user", message)], property_manager.list(cid),
        message, conversation_id=cid,
    )

    assert resolution.property_id == residence.id
    assert resolution.reality_type == "LAYOUT"
    if action_type == "USER_REALITY":
        binding = resolution.action_reality_return
        assert binding is not None
        assert binding.action_id == action.id
        assert binding.reality_need_id == need.id
        assert binding.possible_life_id == possible_life.id
        assert binding.residence_property_id == residence.id
        assert binding.claim_quote == "两室一厅"
        assert possible_life_reality_action_store.get(cid, need.id) == action
    else:
        assert action.action_type == PossibleLifeRealityActionType.PUBLIC_EVIDENCE
        assert resolution.action_reality_return is None
    # Binding is a claim context; it never admits the stated layout.
    assert property_manager.get_scoped(residence.id or "", cid).layout_expression is None


def test_unrelated_or_ambiguous_input_does_not_bind_action() -> None:
    cid = uuid_for("action-return-unrelated")
    residence, _, _, _, _, need = setup_need(
        cid, RealityNeedResolutionMode.REAL_WORLD_CONTACT,
    )
    assert PossibleLifeRealityActionService(
        intelligence=ActionIntelligence("USER_REALITY"),
    ).form(cid, need) is not None
    title = residence.title or ""
    service = UserRealityReturn(intelligence=ExpressionIntelligence(
        property_id=residence.id or "", title=title,
    ))
    for message in ("另一套房实际是两室一厅", f"{title}的户型还没确认"):
        result = service.resolve_expression(
            [ConversationMessage("user", message)], property_manager.list(cid),
            message, conversation_id=cid,
        )
        assert result.action_reality_return is None
    assert property_manager.get_scoped(residence.id or "", cid).layout_expression is None


def test_action_identity_from_another_possible_life_is_not_bound(monkeypatch) -> None:
    cid = uuid_for("action-return-other-possible-life")
    residence, _, _, _, _, need = setup_need(
        cid, RealityNeedResolutionMode.REAL_WORLD_CONTACT,
    )
    action = PossibleLifeRealityActionService(
        intelligence=ActionIntelligence("USER_REALITY"),
    ).form(cid, need)
    assert action is not None
    monkeypatch.setattr(
        possible_life_reality_action_store, "get",
        lambda _cid, _need_id: replace(
            action, possible_life_id=uuid_for("another-possible-life"),
        ),
    )
    title = residence.title or ""
    message = f"{title}这套房实际是两室一厅"
    result = UserRealityReturn(intelligence=ExpressionIntelligence(
        property_id=residence.id or "", title=title,
    )).resolve_expression(
        [ConversationMessage("user", message)], property_manager.list(cid),
        message, conversation_id=cid,
    )
    assert result.property_id == residence.id
    assert result.action_reality_return is None


def test_property_only_reality_return_keeps_existing_admission_path() -> None:
    cid = uuid_for("action-return-property-only")
    residence, _, _, _, _, _ = setup_need(
        cid, RealityNeedResolutionMode.USER_ANSWERABLE,
    )
    title = residence.title or ""
    service = UserRealityReturn(intelligence=ExpressionIntelligence(
        property_id=residence.id or "", title=title,
    ))
    message = f"{title}这套房实际是两室一厅"
    result = service.resolve_expression(
        [ConversationMessage("user", message)], property_manager.list(cid),
        message, conversation_id=cid,
    )
    assert result.property_id == residence.id
    assert result.action_reality_return is None
    admitted = service.admit(
        cid, result.property_id or "", message,
        expected_reality_type=result.reality_type,
    )
    assert admitted is not None
    assert admitted.layout_expression == "两室一厅"
    assert admitted.layout_source == "USER_PROVIDED"
