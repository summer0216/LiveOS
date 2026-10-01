import json

import pytest
from app.models.possible_life_meaningful_unknown import PossibleLifeMeaningfulUnknown
from app.models.profile_patch import LivingProfilePatch
from app.models.reality_need import RealityNeedResolutionMode
from app.services.possible_life_reality_need import PossibleLifeRealityNeedService
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.stores.runtime import (
    decision_action_state_store,
    living_time_relationship_store,
    possible_life_meaningful_unknown_store,
    possible_life_personal_meaning_store,
    possible_life_store,
    reality_need_store,
    work_subject_store,
)
from tests.ids import uuid_for
from tests.test_possible_life_meaningful_unknown import authoritative_possible_life


class NeedIntelligence:
    def __init__(self, mode: str, known_reference: str | None = None) -> None:
        self.mode = mode
        self.known_reference = known_reference
        self.prompts: list[str] = []

    def generate_json(self, prompt: str, **_kwargs) -> str:
        self.prompts.append(prompt)
        context = json.loads(prompt.split("Context: ", 1)[1])
        return json.dumps({
            "possible_life_id": context["possible_life_id"],
            "meaningful_unknown_id": context["meaningful_unknown_id"],
            "unknown_reference": context["question"],
            "needed_reality": "这套住所的实际户型",
            "resolution_mode": self.mode,
            "known_reality_reference": self.known_reference,
        }, ensure_ascii=False)


def setup_unknown(conversation_id: str):
    residence, relationship, possible_life, meaning = authoritative_possible_life(
        conversation_id, "融科·昆仑巢", current_judgment=None,
    )
    profile_manager.merge(
        conversation_id,
        LivingProfilePatch(layout_requirement="两室一厅"),
        latest_insights=[],
    )
    unknown = possible_life_meaningful_unknown_store.save(
        conversation_id,
        PossibleLifeMeaningfulUnknown(
            id=uuid_for(f"{conversation_id}-unknown"),
            possible_life_id=possible_life.id,
            personal_meaning_id=meaning.id,
            question="这套住所实际是几室几厅？",
            why_it_matters="户型会改变日常居住安排。",
            state_hash="meaningfulness-validated",
        ),
    )
    return residence, relationship, possible_life, meaning, unknown


@pytest.mark.parametrize(
    "mode", ["USER_ANSWERABLE", "REAL_WORLD_CONTACT"],
)
def test_reality_need_persists_without_action_or_source_mutation(mode: str) -> None:
    cid = uuid_for(f"reality-need-{mode}")
    residence, _, possible_life, _, unknown = setup_unknown(cid)
    before = (
        possible_life_store.get(cid, possible_life.id),
        possible_life_personal_meaning_store.get(cid, possible_life.id),
        possible_life_meaningful_unknown_store.get(cid, possible_life.id),
        living_time_relationship_store.get(cid, residence.id or ""),
        property_manager.get_scoped(residence.id or "", cid),
        work_subject_store.get(cid),
    )
    intelligence = NeedIntelligence(mode)
    service = PossibleLifeRealityNeedService(intelligence=intelligence)
    need = service.form(cid, possible_life.id, unknown.id)

    assert need is not None
    assert need == reality_need_store.get(cid, unknown.id)
    assert need.possible_life_id == possible_life.id
    assert need.meaningful_unknown_id == unknown.id
    assert need.needed_reality == "这套住所的实际户型"
    assert need.resolution_mode == RealityNeedResolutionMode(mode)
    assert need.known_reality_reference is None
    assert "两室一厅" in intelligence.prompts[0]
    assert "1min WALKING" in intelligence.prompts[0]
    assert "AMAP_DIRECTION_API" in intelligence.prompts[0]
    assert "一分钟步行通勤" in intelligence.prompts[0]
    assert decision_action_state_store.get(cid) is None
    assert property_manager.get_scoped(residence.id or "", cid).reality_action_type is None
    assert before == (
        possible_life_store.get(cid, possible_life.id),
        possible_life_personal_meaning_store.get(cid, possible_life.id),
        possible_life_meaningful_unknown_store.get(cid, possible_life.id),
        living_time_relationship_store.get(cid, residence.id or ""),
        property_manager.get_scoped(residence.id or "", cid),
        work_subject_store.get(cid),
    )
    assert service.form(cid, possible_life.id, unknown.id) == need
    assert len(intelligence.prompts) == 1


def test_already_known_requires_an_admitted_reality_reference() -> None:
    cid = uuid_for("reality-need-already-known")
    residence, _, possible_life, _, unknown = setup_unknown(cid)
    intelligence = NeedIntelligence("ALREADY_KNOWN", "LAYOUT_REALITY")
    service = PossibleLifeRealityNeedService(intelligence=intelligence)
    assert service.form(cid, possible_life.id, unknown.id) is None
    assert reality_need_store.get(cid, unknown.id) is None

    admitted = property_manager.admit_user_layout_reality(
        residence.id or "", cid, expression="两室一厅",
    )
    assert admitted is not None
    need = service.form(cid, possible_life.id, unknown.id)
    assert need is not None
    assert need.resolution_mode == RealityNeedResolutionMode.ALREADY_KNOWN
    assert need.known_reality_reference == "LAYOUT_REALITY"
    assert need == reality_need_store.get(cid, unknown.id)
    assert decision_action_state_store.get(cid) is None


def test_need_rejects_wrong_unknown_and_non_authoritative_possible_life() -> None:
    cid = uuid_for("reality-need-wrong-reference")
    _, _, possible_life, _, unknown = setup_unknown(cid)
    service = PossibleLifeRealityNeedService(
        intelligence=NeedIntelligence("USER_ANSWERABLE"),
    )
    assert service.form(cid, possible_life.id, uuid_for("other-unknown")) is None
    assert service.form(cid, uuid_for("other-life"), unknown.id) is None
    assert reality_need_store.get(cid, unknown.id) is None


def test_reality_need_is_not_formed_from_missing_data_alone() -> None:
    cid = uuid_for("reality-need-no-meaningful-unknown")
    _, _, possible_life, _ = authoritative_possible_life(
        cid, "融科·昆仑巢", current_judgment=None,
    )
    intelligence = NeedIntelligence("USER_ANSWERABLE")
    assert PossibleLifeRealityNeedService(intelligence=intelligence).form(
        cid, possible_life.id, uuid_for("missing-unknown"),
    ) is None
    assert intelligence.prompts == []
