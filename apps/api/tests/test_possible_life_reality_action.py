import json

import pytest
from app.models.possible_life_reality_action import (
    PossibleLifeRealityAction,
    PossibleLifeRealityActionType,
)
from app.models.reality_need import RealityNeed, RealityNeedResolutionMode
from app.services.possible_life_reality_action import PossibleLifeRealityActionService
from app.services.property_manager import property_manager
from app.stores.runtime import (
    decision_action_state_store,
    living_time_relationship_store,
    possible_life_meaningful_unknown_store,
    possible_life_personal_meaning_store,
    possible_life_reality_action_store,
    possible_life_store,
    reality_need_store,
)
from tests.ids import uuid_for
from tests.test_possible_life_reality_need import setup_unknown


class ActionIntelligence:
    def __init__(self, action_type: str) -> None:
        self.action_type = action_type
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, **_kwargs) -> str:
        self.prompts.append(prompt)
        context = json.loads(prompt.split("Context: ", 1)[1])
        label = (
            "核对可追溯房源资料中的实际户型"
            if self.action_type == "PUBLIC_EVIDENCE"
            else "联系房东并核验该套房的实际户型"
        )
        return json.dumps({
            "possible_life_id": context["possible_life_id"],
            "reality_need_id": context["reality_need_id"],
            "needed_reality_reference": context["needed_reality"],
            "action_type": self.action_type,
            "action_label": label,
            "why_this_action": "需要核实具体房屋的户型事实。",
        }, ensure_ascii=False)


def setup_need(cid: str, mode: RealityNeedResolutionMode):
    residence, relationship, possible_life, meaning, unknown = setup_unknown(cid)
    if mode == RealityNeedResolutionMode.ALREADY_KNOWN:
        assert property_manager.admit_user_layout_reality(
            residence.id or "", cid, expression="两室一厅",
        ) is not None
    need = reality_need_store.save(
        cid,
        RealityNeed(
            id=uuid_for(f"{cid}-need"),
            possible_life_id=possible_life.id,
            meaningful_unknown_id=unknown.id,
            needed_reality="这套住所的实际户型",
            resolution_mode=mode,
            known_reality_reference=(
                "LAYOUT_REALITY"
                if mode == RealityNeedResolutionMode.ALREADY_KNOWN else None
            ),
            state_hash="admitted-need-state",
        ),
    )
    return residence, relationship, possible_life, meaning, unknown, need


@pytest.mark.parametrize("action_type", ["PUBLIC_EVIDENCE", "USER_REALITY"])
def test_contact_need_forms_authoritative_action_without_reality_mutation(
    action_type: str,
) -> None:
    cid = uuid_for(f"possible-life-reality-action-{action_type}")
    residence, relationship, possible_life, meaning, unknown, need = setup_need(
        cid, RealityNeedResolutionMode.REAL_WORLD_CONTACT,
    )
    before = (
        possible_life_store.get(cid, possible_life.id),
        possible_life_personal_meaning_store.get(cid, possible_life.id),
        possible_life_meaningful_unknown_store.get(cid, possible_life.id),
        reality_need_store.get(cid, unknown.id),
        living_time_relationship_store.get(cid, residence.id or ""),
        property_manager.get_scoped(residence.id or "", cid),
    )
    intelligence = ActionIntelligence(action_type)
    service = PossibleLifeRealityActionService(intelligence=intelligence)
    action = service.form(cid, need)

    assert action is not None
    assert action == possible_life_reality_action_store.get(cid, need.id)
    assert action.possible_life_id == possible_life.id
    assert action.reality_need_id == need.id
    assert action.action_type == PossibleLifeRealityActionType(action_type)
    assert "REAL_WORLD_CONTACT" in intelligence.prompts[0]
    assert "Merely asking for a fact the user already knows is not USER_REALITY" in (
        intelligence.prompts[0]
    )
    assert decision_action_state_store.get(cid) is None
    assert property_manager.get_scoped(residence.id or "", cid).reality_action_type is None
    assert property_manager.get_scoped(residence.id or "", cid).layout_expression is None
    assert before == (
        possible_life_store.get(cid, possible_life.id),
        possible_life_personal_meaning_store.get(cid, possible_life.id),
        possible_life_meaningful_unknown_store.get(cid, possible_life.id),
        reality_need_store.get(cid, unknown.id),
        living_time_relationship_store.get(cid, residence.id or ""),
        property_manager.get_scoped(residence.id or "", cid),
    )
    assert relationship == living_time_relationship_store.get(cid, residence.id or "")
    assert meaning == possible_life_personal_meaning_store.get(cid, possible_life.id)
    assert service.form(cid, need) == action
    assert len(intelligence.prompts) == 1


@pytest.mark.parametrize(
    "mode", [RealityNeedResolutionMode.ALREADY_KNOWN,
             RealityNeedResolutionMode.USER_ANSWERABLE],
)
def test_non_contact_need_never_forms_action(mode: RealityNeedResolutionMode) -> None:
    cid = uuid_for(f"possible-life-action-gate-{mode.value}")
    _, _, possible_life, _, _, need = setup_need(cid, mode)
    intelligence = ActionIntelligence("USER_REALITY")
    assert PossibleLifeRealityActionService(intelligence=intelligence).form(
        cid, need,
    ) is None
    assert possible_life_reality_action_store.get(cid, need.id) is None
    assert intelligence.prompts == []
    with pytest.raises(ValueError, match="REAL_WORLD_CONTACT"):
        possible_life_reality_action_store.save(
            cid,
            PossibleLifeRealityAction(
                id=uuid_for(f"invalid-action-{mode.value}"),
                possible_life_id=possible_life.id,
                reality_need_id=need.id,
                action_type=PossibleLifeRealityActionType.USER_REALITY,
                label="联系房东核验户型",
                why="需要实际核验",
                state_hash="invalid-mode",
            ),
        )


def test_mode_change_removes_stale_contact_action() -> None:
    cid = uuid_for("possible-life-action-mode-change")
    _, _, possible_life, _, unknown, need = setup_need(
        cid, RealityNeedResolutionMode.REAL_WORLD_CONTACT,
    )
    intelligence = ActionIntelligence("PUBLIC_EVIDENCE")
    service = PossibleLifeRealityActionService(intelligence=intelligence)
    assert service.form(cid, need) is not None
    changed_need = reality_need_store.save(
        cid,
        RealityNeed(
            id=need.id,
            possible_life_id=possible_life.id,
            meaningful_unknown_id=unknown.id,
            needed_reality=need.needed_reality,
            resolution_mode=RealityNeedResolutionMode.USER_ANSWERABLE,
            known_reality_reference=None,
            state_hash="need-now-user-answerable",
        ),
    )
    assert possible_life_reality_action_store.get(cid, need.id) is None
    assert service.form(cid, changed_need) is None
    assert possible_life_reality_action_store.get(cid, need.id) is None
    assert len(intelligence.prompts) == 1


def test_store_rejects_action_with_inconsistent_possible_life_reference() -> None:
    cid = uuid_for("possible-life-action-wrong-reference")
    _, _, _, _, _, need = setup_need(
        cid, RealityNeedResolutionMode.REAL_WORLD_CONTACT,
    )
    with pytest.raises(ValueError, match="same Possible Life"):
        possible_life_reality_action_store.save(
            cid,
            PossibleLifeRealityAction(
                id=uuid_for("invalid-action"),
                possible_life_id=uuid_for("other-possible-life"),
                reality_need_id=need.id,
                action_type=PossibleLifeRealityActionType.PUBLIC_EVIDENCE,
                label="核对房源资料",
                why="核实户型",
                state_hash="invalid-reference",
            ),
        )
    assert possible_life_reality_action_store.get(cid, need.id) is None
