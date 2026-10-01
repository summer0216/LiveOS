import json
from concurrent.futures import Future, ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from app.models.conversation import ConversationMessage
from app.models.decision_geography import DecisionGeography
from app.models.living_time import LivingTimeRelationship
from app.models.possible_life import PossibleLife
from app.models.possible_life_meaningful_unknown import PossibleLifeMeaningfulUnknown
from app.models.possible_life_personal_meaning import PossibleLifePersonalMeaning
from app.models.profile import LivingProfile
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    Property,
)
from app.models.reality_need import RealityNeed, RealityNeedResolutionMode
from app.models.work_subject import WorkSubject
from app.services.chat_service import WorldConsequenceReady, chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_geography_service import decision_geography_service
from app.services.decision_signal_intelligence import decision_signal_intelligence
from app.services.living_meaning_service import living_meaning_service
from app.services.possible_life_meaningful_unknown import (
    possible_life_meaningful_unknown_service,
)
from app.services.possible_life_reality_action import (
    possible_life_reality_action_service,
)
from app.services.possible_life_reality_need import possible_life_reality_need_service
from app.services.profile_intelligence import BudgetRealityAudit, profile_intelligence
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.services.user_reality_return import (
    PossibleLifeAttentionTarget,
    PropertyExpressionResolution,
    UserRealityReturn,
    user_reality_return,
)
from app.stores.runtime import (
    living_time_relationship_store,
    possible_life_personal_meaning_store,
    possible_life_store,
    profile_store,
    work_subject_store,
)
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_terse_layout_answer_uses_active_unknown_context_only():
    home = Property(
        id="home-1", conversation_id="conversation-1", title="龙湖时代天街",
        geographic_status=GeographicStatus.GROUNDED,
        meaningful_unknown="龙湖时代天街这套房的实际户型是几室几厅？",
        meaningful_unknown_state_hash="unknown-hash",
    )

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            assert "a terse direct layout answer is PROPERTY_REALITY / LAYOUT" in prompt
            return json.dumps({
                # Reproduce the live semantic misclassification: the boundary
                # must route only the active layout answer to existing admission.
                "claim_nature": "PERSONAL_REQUIREMENT",
                "layout_requirement": "两室一厅。",
                "reality_type": None,
                "claim_quote": None,
                "property_id": None,
                "binding_evidence": None,
                "binding_source": None,
                "attention_property_id": None,
                "attention_evidence": None,
            }, ensure_ascii=False)

    service = UserRealityReturn(intelligence=Intelligence())
    history = [ConversationMessage("user", "两室一厅。")]
    answer = service.resolve_expression(
        history, [home], "两室一厅。", focused_property_id=home.id,
    )
    assert answer.property_id == home.id and answer.reality_type == "LAYOUT"
    assert answer.layout_requirement is None

    home.meaningful_unknown = None
    home.meaningful_unknown_state_hash = None
    requirement = service.resolve_expression(
        history, [home], "两室一厅。", focused_property_id=home.id,
    )
    assert requirement.property_id is None and requirement.reality_type is None
    assert requirement.layout_requirement == "两室一厅。"


def test_authoritative_work_subject_can_become_attention_target():
    cid = uuid_for("authoritative-work-subject-attention")
    create_owned_conversation(TestClient(app), cid)
    subject = work_subject_store.save(cid, WorkSubject(
        identity="融科资讯中心",
        geographic_identity="北京市海淀区融科资讯中心",
        geographic_precision="PLACE",
        geographic_status="GROUNDED",
        lng=116.316176,
        lat=39.982403,
    ))

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            assert '"identity": "融科资讯中心"' in prompt
            return json.dumps({
                "claim_nature": "OTHER",
                "layout_requirement": None,
                "reality_type": None,
                "claim_quote": None,
                "property_id": None,
                "binding_evidence": None,
                "binding_source": None,
                "attention_property_id": None,
                "attention_evidence": None,
                "attention_subject_identity": "融科资讯中心",
                "attention_subject_evidence": "具体工作地点是融科资讯中心",
            }, ensure_ascii=False)

    resolution = UserRealityReturn(intelligence=Intelligence()).resolve_expression(
        [
            ConversationMessage("user", "具体工作地点是融科资讯中心"),
            ConversationMessage("user", "这里的通勤情况怎么样？"),
        ],
        [],
        "这里的通勤情况怎么样？",
        conversation_id=cid,
    )

    assert resolution.attention_subject == subject
    assert resolution.attention_property_id is None


def test_authoritative_possible_life_meaning_can_become_attention_target():
    cid = uuid_for("authoritative-possible-life-meaning-attention")
    create_owned_conversation(TestClient(app), cid)
    subject = work_subject_store.save(cid, WorkSubject(
        identity="融科资讯中心",
        geographic_identity="北京市海淀区融科资讯中心",
        geographic_precision="PLACE",
        geographic_status="GROUNDED",
        lng=116.316176,
        lat=39.982403,
    ))
    owner_id = possible_life_store.owner_id(cid)
    assert owner_id is not None

    possible_lives = []
    meanings = []
    homes = []
    for index, (title, minutes) in enumerate((("融科·昆仑巢", 1), ("新科祥园", 5))):
        home = property_manager.create(cid, Property(
            title=title,
            geographic_identity=f"北京市海淀区{title}",
            geographic_precision=GeographicPrecision.COMMUNITY,
            geographic_status=GeographicStatus.GROUNDED,
            lng=116.31 + index * 0.01,
            lat=39.98,
        ))
        assert home.id is not None
        living_time_relationship_store.save(cid, LivingTimeRelationship(
            residence_property_id=home.id,
            residence_identity=home.title,
            residence_geographic_identity=home.geographic_identity or "",
            work_subject_identity=subject.identity,
            work_geographic_identity=subject.geographic_identity,
            travel_minutes=minutes,
            travel_mode=CommuteMode.WALKING,
            evidence_source="AMAP_DIRECTION_API",
            evidence_reference=f"route-{index}",
        ))
        possible_life = possible_life_store.save(cid, PossibleLife(
            id=uuid_for(f"possible-life-attention-{index}"),
            work_subject_owner_id=owner_id,
            residence_property_id=home.id,
            living_time_residence_property_id=home.id,
            personal_meaning_reference="living_profile.commute_minutes",
        ))
        meaning = possible_life_personal_meaning_store.save(
            cid,
            PossibleLifePersonalMeaning(
                id=uuid_for(f"possible-life-attention-meaning-{index}"),
                possible_life_id=possible_life.id,
                meaning=f"{minutes}分钟步行通勤符合当前生活约束。",
                living_time_residence_property_id=home.id,
                actual_travel_minutes=minutes,
                actual_travel_mode=CommuteMode.WALKING,
                route_evidence_source="AMAP_DIRECTION_API",
                route_evidence_reference=f"route-{index}",
                requirement_reference="living_profile.commute_minutes",
                maximum_commute_minutes=30,
                requirement_satisfied=True,
            ),
        )
        homes.append(home)
        possible_lives.append(possible_life)
        meanings.append(meaning)

    before_lives = possible_life_store.list(cid)
    before_meanings = possible_life_personal_meaning_store.list(cid)

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            assert possible_lives[0].id in prompt
            assert possible_lives[1].id in prompt
            assert meanings[0].meaning in prompt
            assert meanings[1].meaning in prompt
            assert "do not rank, score, recommend" in prompt
            return json.dumps({
                "claim_nature": "OTHER",
                "layout_requirement": None,
                "reality_type": None,
                "claim_quote": None,
                "property_id": None,
                "binding_evidence": None,
                "binding_source": None,
                "attention_property_id": None,
                "attention_evidence": None,
                "attention_subject_identity": None,
                "attention_subject_evidence": None,
                "attention_possible_life_id": possible_lives[0].id,
                "attention_possible_life_evidence": "最值得我现在关注",
            }, ensure_ascii=False)

    resolution = UserRealityReturn(intelligence=Intelligence()).resolve_expression(
        [ConversationMessage("user", "这个1分钟通勤的生活最值得我现在关注")],
        homes,
        "这个1分钟通勤的生活最值得我现在关注",
        conversation_id=cid,
    )

    target = resolution.attention_possible_life
    assert target is not None
    assert target.possible_life == possible_lives[0]
    assert target.possible_life.id == possible_lives[0].id
    assert target.personal_meaning == meanings[0]
    assert not hasattr(target, "score")
    assert not hasattr(target, "rank")

    class NullPossibleLifeSelectionIntelligence:
        def generate_json(self, _prompt, **_kwargs):
            return json.dumps({
                "claim_nature": "OTHER",
                "layout_requirement": None,
                "reality_type": None,
                "claim_quote": None,
                "property_id": None,
                "binding_evidence": None,
                "binding_source": None,
                "attention_property_id": None,
                "attention_evidence": None,
                "attention_subject_identity": None,
                "attention_subject_evidence": None,
                "attention_possible_life_id": None,
                "attention_possible_life_evidence": None,
            }, ensure_ascii=False)

    fallback_service = UserRealityReturn(
        intelligence=NullPossibleLifeSelectionIntelligence(),
    )
    explicit_text = "我现在明确关注融科昆仑巢对应的可能生活。"
    explicit = fallback_service.resolve_expression(
        [ConversationMessage("user", explicit_text)],
        homes,
        explicit_text,
        conversation_id=cid,
    )
    assert explicit.attention_possible_life is not None
    assert explicit.attention_possible_life.possible_life.id == possible_lives[0].id
    assert explicit.attention_possible_life.personal_meaning == meanings[0]

    ambiguous_text = "我还在考虑融科·昆仑巢和新科祥园这两个可能生活。"
    ambiguous = fallback_service.resolve_expression(
        [ConversationMessage("user", ambiguous_text)],
        homes,
        ambiguous_text,
        conversation_id=cid,
    )
    assert ambiguous.attention_possible_life is None

    unrelated_text = "融科·昆仑巢今天附近天气不错。"
    unrelated = fallback_service.resolve_expression(
        [ConversationMessage("user", unrelated_text)],
        homes,
        unrelated_text,
        conversation_id=cid,
    )
    assert unrelated.attention_possible_life is None

    rejected_text = "我不关注融科·昆仑巢对应的可能生活。"
    rejected = fallback_service.resolve_expression(
        [ConversationMessage("user", rejected_text)],
        homes,
        rejected_text,
        conversation_id=cid,
    )
    assert rejected.attention_possible_life is None
    assert possible_life_store.list(cid) == before_lives
    assert possible_life_personal_meaning_store.list(cid) == before_meanings


def test_property_attention_remains_supported_with_subject_attention_fields():
    home = Property(
        id="home-attention-1", conversation_id="conversation-attention-1",
        title="龙湖时代天街", geographic_status=GeographicStatus.GROUNDED,
    )

    class Intelligence:
        def generate_json(self, _prompt, **_kwargs):
            return json.dumps({
                "claim_nature": "PERSONAL_REQUIREMENT",
                "layout_requirement": "两室一厅",
                "reality_type": None,
                "claim_quote": None,
                "property_id": None,
                "binding_evidence": None,
                "binding_source": None,
                "attention_property_id": home.id,
                "attention_evidence": "我想住龙湖时代天街",
                "attention_subject_identity": None,
                "attention_subject_evidence": None,
            }, ensure_ascii=False)

    resolution = UserRealityReturn(intelligence=Intelligence()).resolve_expression(
        [
            ConversationMessage("user", "我想住龙湖时代天街"),
            ConversationMessage("user", "还要两室一厅"),
        ],
        [home],
        "还要两室一厅",
    )

    assert resolution.attention_property_id == home.id
    assert resolution.attention_subject is None


def test_layout_admission_accepts_only_matching_active_layout_unknown_reference():
    client = TestClient(app)
    matching_cid = uuid_for("matching-layout-unknown-reference")
    mismatched_cid = uuid_for("mismatched-layout-unknown-reference")
    question = "该房源实际是几室几厅？"

    class Intelligence:
        def __init__(self, unknown_reference):
            self._unknown_reference = unknown_reference

        def generate_json(self, _prompt, **_kwargs):
            return json.dumps({
                "unknown_reference": self._unknown_reference,
                "reality_type": "LAYOUT",
                "value": "两室一厅",
            }, ensure_ascii=False)

    for cid in (matching_cid, mismatched_cid):
        create_owned_conversation(client, cid)
    matching = property_manager.create(matching_cid, Property(
        title="龙湖时代天街", geographic_status=GeographicStatus.GROUNDED,
        meaningful_unknown=question, meaningful_unknown_state_hash="layout-question",
    ))
    mismatched = property_manager.create(mismatched_cid, Property(
        title="另一处住所", geographic_status=GeographicStatus.GROUNDED,
        meaningful_unknown=question, meaningful_unknown_state_hash="layout-question",
    ))

    admitted = UserRealityReturn(intelligence=Intelligence(question)).admit(
        matching_cid, matching.id, "两室一厅。", expected_reality_type="LAYOUT",
    )
    assert admitted is not None
    assert property_manager.get_scoped(matching.id, matching_cid).layout_expression == "两室一厅"

    rejected = UserRealityReturn(intelligence=Intelligence("另一处房源实际是几室几厅？")).admit(
        mismatched_cid, mismatched.id, "两室一厅。", expected_reality_type="LAYOUT",
    )
    assert rejected is None
    assert property_manager.get_scoped(mismatched.id, mismatched_cid).layout_expression is None


def test_stream_fallback_resolution_receives_focused_layout_context(monkeypatch):
    """The deferred resolution path must retain the already-authoritative Focus."""
    cid = uuid_for("focused-layout-stream-context")
    create_owned_conversation(TestClient(app), cid)
    home = property_manager.create(cid, Property(
        title="龙湖时代天街", geographic_status=GeographicStatus.GROUNDED,
        meaningful_unknown="该房源实际是几室几厅？",
        meaningful_unknown_state_hash="layout-unknown-hash",
    ))
    history = [ConversationMessage("user", "两室一厅。")]
    profile_future: Future[ProfileAnalysis] = Future()
    profile_future.set_result(ProfileAnalysis(patch=LivingProfilePatch()))
    executor = ThreadPoolExecutor(max_workers=1)
    seen_focus_ids: list[str | None] = []

    def resolve(
        _history, _properties, _message, *, focused_property_id=None,
        conversation_id=None,
    ):
        assert conversation_id == cid
        seen_focus_ids.append(focused_property_id)
        return PropertyExpressionResolution(home.id, "LAYOUT")

    monkeypatch.setattr(user_reality_return, "resolve_expression", resolve)
    monkeypatch.setattr(user_reality_return, "admit", lambda *_args, **_kwargs: home)
    monkeypatch.setattr(chat_service, "_update_profile", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *_args: iter(["reply"]))
    monkeypatch.setattr(living_meaning_service, "form", lambda *_args: home)

    list(chat_service._complete_stream_turn(
        cid, history, None, profile_future, executor, False, None,
        focused_property_id=home.id,
    ))

    assert seen_focus_ids == [home.id]


def test_attention_targets_produce_matching_focus_consequences(monkeypatch):
    cid = uuid_for("attention-target-focus-consequence")
    create_owned_conversation(TestClient(app), cid)
    authoritative_subject = work_subject_store.save(cid, WorkSubject(
        identity="融科资讯中心",
        geographic_identity="北京市海淀区融科资讯中心",
        geographic_precision="PLACE",
        geographic_status="GROUNDED",
        lng=116.316176,
        lat=39.982403,
    ))
    home = property_manager.create(cid, Property(
        title="龙湖时代天街",
        geographic_identity="北京市龙湖时代天街",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.31,
        lat=39.98,
    ))
    assert home.id is not None
    relationship = living_time_relationship_store.save(
        cid,
        LivingTimeRelationship(
            residence_property_id=home.id,
            residence_identity=home.title,
            residence_geographic_identity=home.geographic_identity or "",
            work_subject_identity=authoritative_subject.identity,
            work_geographic_identity=authoritative_subject.geographic_identity,
            travel_minutes=8,
            travel_mode=CommuteMode.WALKING,
            evidence_source="AMAP_DIRECTION_API",
            evidence_reference="route-consequence",
        ),
    )
    owner_id = possible_life_store.owner_id(cid)
    assert owner_id is not None
    possible_life = possible_life_store.save(
        cid,
        PossibleLife(
            id=uuid_for("possible-life-focus-consequence"),
            work_subject_owner_id=owner_id,
            residence_property_id=home.id,
            living_time_residence_property_id=relationship.residence_property_id,
            personal_meaning_reference="living_profile.commute_minutes",
        ),
    )
    personal_meaning = possible_life_personal_meaning_store.save(
        cid,
        PossibleLifePersonalMeaning(
            id=uuid_for("possible-life-focus-consequence-meaning"),
            possible_life_id=possible_life.id,
            meaning="8分钟步行通勤让日常安排保持从容。",
            living_time_residence_property_id=relationship.residence_property_id,
            actual_travel_minutes=relationship.travel_minutes,
            actual_travel_mode=relationship.travel_mode,
            route_evidence_source=relationship.evidence_source,
            route_evidence_reference=relationship.evidence_reference,
            requirement_reference="living_profile.commute_minutes",
            maximum_commute_minutes=30,
            requirement_satisfied=True,
        ),
    )
    possible_life_target = PossibleLifeAttentionTarget(
        possible_life=possible_life,
        personal_meaning=personal_meaning,
    )
    possible_lives_before = possible_life_store.list(cid)
    meanings_before = possible_life_personal_meaning_store.list(cid)
    history = [ConversationMessage("user", "继续考虑这个地方")]
    unknown_focus_ids: list[str] = []
    need_focus_ids: list[tuple[str, str]] = []
    action_need_ids: list[str] = []
    unknown = PossibleLifeMeaningfulUnknown(
        id=uuid_for("possible-life-focus-consequence-unknown"),
        possible_life_id=possible_life.id,
        personal_meaning_id=personal_meaning.id,
        question="这套住所实际是几室几厅？",
        why_it_matters="户型会改变居住意义。",
        state_hash="focused-unknown",
    )
    need = RealityNeed(
        id=uuid_for("possible-life-focus-consequence-need"),
        possible_life_id=possible_life.id,
        meaningful_unknown_id=unknown.id,
        needed_reality="这套住所的实际户型",
        resolution_mode=RealityNeedResolutionMode.REAL_WORLD_CONTACT,
        known_reality_reference=None,
        state_hash="focused-need",
    )

    monkeypatch.setattr(chat_service, "_update_profile", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *_args: iter(["reply"]))
    monkeypatch.setattr(
        possible_life_meaningful_unknown_service,
        "form",
        lambda _cid, possible_life_id: (
            unknown_focus_ids.append(possible_life_id) or unknown
        ),
    )
    monkeypatch.setattr(
        possible_life_reality_need_service,
        "form",
        lambda _cid, possible_life_id, unknown_id: (
            need_focus_ids.append((possible_life_id, unknown_id)) or need
        ),
    )
    monkeypatch.setattr(
        possible_life_reality_action_service,
        "form",
        lambda _cid, reality_need: action_need_ids.append(reality_need.id),
    )

    def complete(resolution):
        profile_future: Future[ProfileAnalysis] = Future()
        profile_future.set_result(ProfileAnalysis(patch=LivingProfilePatch()))
        return list(chat_service._complete_stream_turn(
            cid, history, None, profile_future, ThreadPoolExecutor(max_workers=1),
            False, None, property_resolution=resolution,
        ))

    subject_events = complete(PropertyExpressionResolution(
        attention_subject=authoritative_subject,
    ))
    subject_focus = next(
        event for event in subject_events
        if isinstance(event, WorldConsequenceReady) and event.focus_subject is not None
    )
    assert subject_focus.focus_subject is authoritative_subject
    assert subject_focus.focus_property_id is None

    property_events = complete(PropertyExpressionResolution(
        attention_property_id=home.id,
    ))
    property_focus = next(
        event for event in property_events
        if isinstance(event, WorldConsequenceReady) and event.focus_property_id is not None
    )
    assert property_focus.focus_property_id == home.id
    assert property_focus.focus_subject is None

    possible_life_events = complete(PropertyExpressionResolution(
        attention_possible_life=possible_life_target,
    ))
    possible_life_focus = next(
        event for event in possible_life_events
        if (
            isinstance(event, WorldConsequenceReady)
            and event.focus_possible_life is not None
        )
    )
    assert possible_life_focus.focus_possible_life is possible_life_target
    assert possible_life_focus.focus_possible_life.possible_life is possible_life
    assert possible_life_focus.focus_possible_life.personal_meaning is personal_meaning
    assert possible_life_focus.focus_property_id is None
    assert possible_life_focus.focus_subject is None
    assert unknown_focus_ids == [possible_life.id]
    assert need_focus_ids == [(possible_life.id, unknown.id)]
    assert action_need_ids == [need.id]
    assert possible_life_store.list(cid) == possible_lives_before
    assert possible_life_personal_meaning_store.list(cid) == meanings_before


def test_expression_context_resolution_precedes_property_admission(monkeypatch):
    client = TestClient(app)
    requirement_cid = uuid_for("expression-requirement")
    explicit_cid = uuid_for("expression-explicit-property")
    continuity_cid = uuid_for("expression-continuity")
    ambiguous_cid = uuid_for("expression-ambiguous")
    focused_cid = uuid_for("expression-focused")
    ids = (requirement_cid, explicit_cid, continuity_cid, ambiguous_cid, focused_cid)
    homes = {}
    for cid in ids:
        create_owned_conversation(client, cid)
        profile_store.save(cid, LivingProfile())
        homes[cid] = property_manager.create(cid, Property(
            title="龙湖时代天街", geographic_identity="成都市龙湖时代天街",
            geographic_precision=GeographicPrecision.PLACE,
            geographic_status=GeographicStatus.GROUNDED,
            lng=103.920730, lat=30.753792,
        ))
    for cid in (requirement_cid, continuity_cid):
        conversation_manager.append_user_message(cid, "我想住龙湖时代天街")
    conversation_manager.append_user_message(ambiguous_cid, "我想住龙湖时代天街和另一处住所")
    property_manager.create(ambiguous_cid, Property(
        title="另一处住所", geographic_identity="成都市另一处住所",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.921, lat=30.754,
    ))

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            if "Grounded residences:" in prompt:
                current = prompt.split("Current message: ", 1)[1].split("\n", 1)[0]
                requirement = "预算2000，两室一厅" in current
                focus = 'Focused residence id (context evidence only): "' in prompt
                explicit = "龙湖时代天街这个住所" in current
                continuity = "我想住龙湖时代天街" in prompt
                ambiguous = "另一处住所" in prompt
                evidence = (
                    "龙湖时代天街这个住所" if explicit else
                    "我想住龙湖时代天街" if continuity else None
                )
                return json.dumps({
                    "claim_nature": "PERSONAL_REQUIREMENT" if requirement else "PROPERTY_REALITY",
                    "layout_requirement": "两室一厅" if requirement else None,
                    "reality_type": None if requirement else "LAYOUT",
                    "claim_quote": None if requirement else "两室一厅",
                    "property_id": None if requirement or (ambiguous and not focus) else (
                        next(home.id for home in homes.values() if home.id in prompt)
                        if focus else homes[explicit_cid].id if explicit else homes[continuity_cid].id
                    ),
                    "binding_evidence": None if requirement or focus else evidence,
                    "binding_source": None if requirement else "FOCUS" if focus else "USER_EXPRESSION",
                    "attention_property_id": (
                        homes[requirement_cid].id if requirement else
                        homes[ambiguous_cid].id if ambiguous else
                        homes[explicit_cid].id if explicit else None
                    ),
                    "attention_evidence": (
                        "我想住龙湖时代天街" if requirement else
                        "我想住龙湖时代天街和另一处住所" if ambiguous else
                        "龙湖时代天街这个住所" if explicit else None
                    ),
                }, ensure_ascii=False)
            return json.dumps({
                "unknown_reference": None, "reality_type": "LAYOUT", "value": "两室一厅",
            }, ensure_ascii=False)

    monkeypatch.setattr(user_reality_return, "_intelligence", Intelligence())
    monkeypatch.setattr(profile_intelligence, "analyze", lambda *_args, **_kwargs:
                        ProfileAnalysis(patch=LivingProfilePatch(budget=2000)))
    monkeypatch.setattr(decision_signal_intelligence, "analyze", lambda *_args:
                        DecisionGeography())
    monkeypatch.setattr(decision_geography_service, "apply", lambda *args, **kwargs: None)
    monkeypatch.setattr(chat_service, "_update_profile", lambda **kwargs:
                        (profile_manager.merge(kwargs["conversation_id"], LivingProfilePatch(budget=2000), []), ())[1])
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *a: iter(["reply"]))
    reconsidered = []
    monkeypatch.setattr(living_meaning_service, "form", lambda cid, property_id:
                        reconsidered.append((cid, property_id)))

    requirement = client.post("/api/chat/stream", json={
        "conversation_id": requirement_cid, "message": "预算2000，两室一厅",
    })
    assert requirement.status_code == 200
    assert f'"focus_property_id": "{homes[requirement_cid].id}"' in requirement.text
    assert "property-grounding-response" not in requirement.text
    assert property_manager.list(requirement_cid)[0].layout_expression is None
    assert client.get(f"/api/profiles/{requirement_cid}").json()["budget"] == 2000
    assert reconsidered == [(requirement_cid, homes[requirement_cid].id)]

    explicit = client.post("/api/chat/stream", json={
        "conversation_id": explicit_cid, "message": "龙湖时代天街这个住所是两室一厅",
    })
    assert explicit.status_code == 200
    assert "focus_property_id" not in explicit.text
    assert property_manager.list(explicit_cid)[0].layout_expression == "两室一厅"

    continuity = client.post("/api/chat/stream", json={
        "conversation_id": continuity_cid, "message": "这个住所是两室一厅",
    })
    assert continuity.status_code == 200
    assert property_manager.list(continuity_cid)[0].layout_expression == "两室一厅"

    ambiguous = client.post("/api/chat/stream", json={
        "conversation_id": ambiguous_cid, "message": "这个住所是两室一厅",
    })
    assert ambiguous.status_code == 200
    assert "focus_property_id" not in ambiguous.text
    assert "event: property-grounding-response" in ambiguous.text
    assert all(home.layout_expression is None for home in property_manager.list(ambiguous_cid))

    focused_requirement = client.post("/api/chat/stream", json={
        "conversation_id": focused_cid, "message": "预算2000，两室一厅",
        "user_reality_property_id": homes[focused_cid].id,
    })
    assert focused_requirement.status_code == 200
    assert property_manager.list(focused_cid)[0].layout_expression is None

    focused = client.post("/api/chat/stream", json={
        "conversation_id": focused_cid, "message": "这个住所是两室一厅",
        "user_reality_property_id": homes[focused_cid].id,
    })
    assert focused.status_code == 200
    assert property_manager.list(focused_cid)[0].layout_expression == "两室一厅"
    assert len(reconsidered) == 5
    assert all(property_manager.list(cid)[0].rent is None for cid in ids)


def test_focused_layout_statement_persists_without_inventing_rent(monkeypatch):
    client = TestClient(app)
    cid = uuid_for("focused-layout-with-budget")
    create_owned_conversation(client, cid)
    profile_store.save(cid, LivingProfile())
    home = property_manager.create(cid, Property(
        title="龙湖时代天街", geographic_identity="成都市龙湖时代天街",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.920730, lat=30.753792,
    ))
    property_manager.update_living_meaning(
        home.id, cid, meaning="stale meaning", reality_hash="old-layout",
    )
    property_manager.update_current_judgment(
        home.id, cid, judgment="stale judgment", state_hash="old-layout",
    )

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            assert "龙湖时代天街" in prompt
            if "Grounded residences:" in prompt:
                return json.dumps({
                    "claim_nature": "PROPERTY_REALITY", "reality_type": "LAYOUT",
                    "claim_quote": "两室一厅", "property_id": home.id,
                    "binding_evidence": None, "binding_source": "FOCUS",
                }, ensure_ascii=False)
            if 'Current user message: "这个住所是两室一厅，预算2000"' in prompt:
                return json.dumps({
                    "unknown_reference": None, "reality_type": "LAYOUT",
                    "value": "两室一厅",
                }, ensure_ascii=False)
            return json.dumps({
                "unknown_reference": None, "reality_type": "NONE", "value": None,
            })

    monkeypatch.setattr(user_reality_return, "_intelligence", Intelligence())
    monkeypatch.setattr(
        profile_intelligence, "audit_explicit_budget",
        lambda _history: BudgetRealityAudit("CONFIRMED", 2000, "预算2000"),
    )
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *a: iter(["reply"]))
    interpretation = []
    original_form = living_meaning_service.form

    def record_interpretation(conversation_id, property_id):
        current = property_manager.get_scoped(property_id, conversation_id)
        interpretation.append((
            profile_store.get(conversation_id).budget,
            current.layout_expression, current.living_meaning, current.current_judgment,
        ))
        return original_form(conversation_id, property_id)

    monkeypatch.setattr(living_meaning_service, "form", record_interpretation)
    assert user_reality_return.admit(cid, home.id, "我希望两室一厅") is None
    assert property_manager.get_scoped(home.id, cid).layout_expression is None
    response = client.post("/api/chat/stream", json={
        "conversation_id": cid, "message": "这个住所是两室一厅，预算2000",
        "user_reality_property_id": home.id,
    })
    assert response.status_code == 200
    assert response.text.count("world-consequence-ready") == 2
    assert interpretation == [(2000, "两室一厅", None, None)]
    assert client.get(f"/api/profiles/{cid}").json()["budget"] == 2000
    stored = property_manager.get_scoped(home.id, cid)
    assert stored is not None and stored.id == home.id
    assert stored.layout_expression == "两室一厅"
    assert stored.layout_source == "USER_PROVIDED"
    assert stored.rent is None and stored.rent_source is None
    assert stored.living_meaning is None and stored.current_judgment is None
    items = client.get(f"/api/properties?conversation_id={cid}").json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == home.id
    assert items[0]["layout_expression"] == "两室一厅"
    assert items[0]["layout_source"] == "USER_PROVIDED"


def test_active_tenancy_unknown_answer_updates_world(monkeypatch):
    client = TestClient(app)
    cid = uuid_for("tenancy-unknown-return")
    create_owned_conversation(client, cid)
    profile_store.save(cid, LivingProfile())
    home = property_manager.create(cid, Property(
        title="龙湖时代天街", geographic_identity="龙湖时代天街",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.920730, lat=30.753792,
    ))
    property_manager.update_confirmed_rent(home.id, cid, 2200)
    question = "这住所是整租还是与他人合租？"
    property_manager.update_meaningful_unknown(
        home.id, cid, question=question, why="租住方式尚未确认",
        state_hash="tenancy-question",
    )
    meaning = "已确认整租和月租，是否符合个人需要仍未知。"
    judgment = "租住安排已明确，其个人适配性仍待了解。"
    calls = []

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            if "Grounded residences:" in prompt:
                return json.dumps({
                    "claim_nature": "PROPERTY_REALITY", "reality_type": "TENANCY_MODE",
                    "claim_quote": "整租", "property_id": home.id,
                    "binding_evidence": None, "binding_source": "FOCUS",
                }, ensure_ascii=False)
            if "Determine whether the CURRENT user message" in prompt:
                assert question in prompt
                assert 'Current user message: "整租"' in prompt
                assert "龙湖时代天街" in prompt
                return json.dumps({"unknown_reference": question,
                                   "reality_type": "TENANCY_MODE",
                                   "value": "ENTIRE_RENT"})
            assert '"TENANCY_MODE_REALITY": "ENTIRE_RENT"' in prompt
            grounding = [
                {"fact": "TENANCY_MODE_REALITY", "value": "ENTIRE_RENT"},
                {"fact": "RENT_REALITY", "value": "2200 CNY/month"},
            ]
            if "Audit whether EVERY claim" in prompt:
                assert "personal value, pressure, priority, or a trade-off" in prompt
                return json.dumps({"supported": True, "unsupported_claims": []})
            if "Identify the ONE unknown Reality" in prompt:
                calls.append("unknown")
                return "null"
            if "Judge whether the CURRENT Possible Life" in prompt:
                calls.append("readiness")
                return json.dumps({"status": "NEED_MORE_REALITY",
                                   "reason": "个人需要尚未知",
                                   "meaning_reference": meaning,
                                   "judgment_reference": judgment,
                                   "grounding": grounding})
            if "Form one provisional Current Judgment" in prompt:
                calls.append("judgment")
                return json.dumps({"judgment": judgment,
                                   "meaning_reference": meaning,
                                   "grounding": grounding})
            calls.append("meaning")
            return json.dumps({"meaning": meaning, "grounding": grounding})

    intelligence = Intelligence()
    monkeypatch.setattr(user_reality_return, "_intelligence", intelligence)
    monkeypatch.setattr(living_meaning_service, "_intelligence", intelligence)
    monkeypatch.setattr(chat_service, "_update_profile", lambda *a, **kw: None)
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *a: iter(["reply"]))
    response = client.post("/api/chat/stream", json={
        "conversation_id": cid, "message": "整租",
        "user_reality_property_id": home.id,
    })
    assert response.status_code == 200
    assert response.text.count("world-consequence-ready") == 2
    restored = property_manager.get_scoped(home.id, cid)
    assert restored.tenancy_mode == "ENTIRE_RENT"
    assert restored.tenancy_mode_source == "USER_PROVIDED"
    assert restored.meaningful_unknown is None
    assert restored.living_meaning == meaning
    assert restored.current_judgment == judgment
    assert restored.decision_readiness == "NEED_MORE_REALITY"
    assert calls == ["meaning", "judgment", "readiness", "unknown"]
    assert client.get(f"/api/properties?conversation_id={cid}").json()["items"][0]["tenancy_mode"] == "ENTIRE_RENT"


def test_active_bathroom_unknown_answer_updates_world(monkeypatch):
    client = TestClient(app)
    cid = uuid_for("bathroom-unknown-return")
    create_owned_conversation(client, cid)
    profile_store.save(cid, LivingProfile())
    home = property_manager.create(cid, Property(
        title="龙湖时代天街", geographic_identity="龙湖时代天街",
        geographic_precision=GeographicPrecision.PLACE,
        geographic_status=GeographicStatus.GROUNDED,
        lng=103.920730, lat=30.753792,
    ))
    property_manager.update_confirmed_rent(home.id, cid, 2200)
    question = "你租住的房间是否带独立卫生间？"
    property_manager.update_meaningful_unknown(
        home.id, cid, question=question, why="卫生间安排尚未确认",
        state_hash="bathroom-question",
    )
    assert property_manager.admit_user_bathroom_reality(
        home.id, cid, unknown_hash="stale", independent_bathroom=True,
    ) is None
    assert property_manager.get_scoped(home.id, cid).independent_bathroom is None
    property_manager.update_living_meaning(
        home.id, cid, meaning="old meaning", reality_hash="old-world",
    )
    property_manager.update_current_judgment(
        home.id, cid, judgment="old judgment", state_hash="old-world",
    )
    property_manager.update_meaningful_unknown(
        home.id, cid, question=question, why="卫生间安排尚未确认",
        state_hash="bathroom-question",
    )
    meaning = "已确认独立卫生间和月租，是否符合个人需要仍未知。"
    judgment = "卫生间安排已明确，其个人适配性仍待了解。"
    calls = []
    unsupported = "独立卫生间隐私更好，更适合用户，也更划算。"
    rejected = []

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            if "Grounded residences:" in prompt:
                return json.dumps({
                    "claim_nature": "PROPERTY_REALITY",
                    "reality_type": "INDEPENDENT_BATHROOM",
                    "claim_quote": "独立卫生间", "property_id": home.id,
                    "binding_evidence": None, "binding_source": "FOCUS",
                }, ensure_ascii=False)
            if "Determine whether the CURRENT user message" in prompt:
                assert question in prompt
                assert 'Current user message: "独立卫生间"' in prompt
                assert "龙湖时代天街" in prompt
                return json.dumps({"unknown_reference": question,
                                   "reality_type": "INDEPENDENT_BATHROOM",
                                   "value": True})
            assert '"INDEPENDENT_BATHROOM_REALITY": "PRESENT"' in prompt
            grounding = [
                {"fact": "INDEPENDENT_BATHROOM_REALITY", "value": "PRESENT"},
                {"fact": "RENT_REALITY", "value": "2200 CNY/month"},
            ]
            if "Audit whether EVERY claim" in prompt:
                assert "personal value, pressure, priority, or a trade-off" in prompt
                if unsupported in prompt:
                    rejected.append(unsupported)
                    return json.dumps({"supported": False,
                                       "unsupported_claims": [unsupported]})
                return json.dumps({"supported": True, "unsupported_claims": []})
            if "Identify the ONE unknown Reality" in prompt:
                calls.append("unknown")
                return "null"
            if "Judge whether the CURRENT Possible Life" in prompt:
                calls.append("readiness")
                return json.dumps({"status": "NEED_MORE_REALITY",
                                   "reason": "个人需要尚未知",
                                   "meaning_reference": meaning,
                                   "judgment_reference": judgment,
                                   "grounding": grounding})
            if "Form one provisional Current Judgment" in prompt:
                calls.append("judgment")
                return json.dumps({"judgment": judgment,
                                   "meaning_reference": meaning,
                                   "grounding": grounding})
            calls.append("meaning")
            return json.dumps({"meaning": meaning if rejected else unsupported,
                               "grounding": grounding})

    intelligence = Intelligence()
    monkeypatch.setattr(user_reality_return, "_intelligence", intelligence)
    monkeypatch.setattr(living_meaning_service, "_intelligence", intelligence)
    monkeypatch.setattr(chat_service, "_update_profile", lambda *a, **kw: None)
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *a: iter(["reply"]))
    response = client.post("/api/chat/stream", json={
        "conversation_id": cid, "message": "独立卫生间",
        "user_reality_property_id": home.id,
    })
    assert response.status_code == 200
    assert response.text.count("world-consequence-ready") == 2
    restored = property_manager.get_scoped(home.id, cid)
    assert restored.independent_bathroom is True
    assert restored.independent_bathroom_source == "USER_PROVIDED"
    assert restored.meaningful_unknown is None
    assert restored.living_meaning == meaning
    assert restored.current_judgment == judgment
    assert restored.decision_readiness == "NEED_MORE_REALITY"
    assert calls == ["meaning", "meaning", "judgment", "readiness", "unknown"]
    assert rejected == [unsupported]
    assert unsupported not in (restored.living_meaning, restored.current_judgment)
    assert client.get(f"/api/properties?conversation_id={cid}").json()["items"][0]["independent_bathroom"] is True


def test_focused_user_reality_answer_admits_only_answered_unknown(monkeypatch):
    client = TestClient(app)
    conversation_id = uuid_for("user-reality-return")
    create_owned_conversation(client, conversation_id)
    home = property_manager.create(conversation_id, Property(
        title="融科·昆仑巢",
        geographic_identity="北京市融科·昆仑巢",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.32,
        lat=39.98,
    ))
    property_manager.update_meaningful_unknown(
        home.id, conversation_id,
        question="该住所内是否有日常使用的独立厨房？",
        why="影响日常生活安排", state_hash="unknown-kitchen",
    )
    property_manager.update_reality_action(
        home.id, conversation_id,
        action_type="USER_REALITY", label="向房东或中介核实独立厨房",
        why="需要用户确认", state_hash="action-kitchen",
    )

    class Intelligence:
        def generate_json(self, prompt, **_kwargs):
            assert "融科·昆仑巢" in prompt or "另一住所" in prompt
            if "Grounded residences:" in prompt:
                sound = "路上的车声" in prompt
                return json.dumps({
                    "claim_nature": "PROPERTY_REALITY",
                    "reality_type": "INDOOR_SOUND_OBSERVATION" if sound else "INDEPENDENT_KITCHEN",
                    "claim_quote": (
                        "晚上去看了，关窗以后还是能明显听到路上的车声。"
                        if sound else "有独立厨房"
                    ),
                    "property_id": home.id,
                    "binding_evidence": None, "binding_source": "FOCUS",
                }, ensure_ascii=False)
            if "该住所室内噪音水平如何？" in prompt:
                quote = "晚上去看了，关窗以后还是能明显听到路上的车声。"
                answered = quote in prompt
                return json.dumps({
                    "unknown_reference": "该住所室内噪音水平如何？",
                    "reality_type": "INDOOR_SOUND_OBSERVATION" if answered else "NONE",
                    "value": quote if answered else None,
                }, ensure_ascii=False)
            assert "该住所内是否有日常使用的独立厨房？" in prompt
            answered = "我问了，有独立厨房。" in prompt
            return json.dumps({
                "unknown_reference": "该住所内是否有日常使用的独立厨房？",
                "reality_type": "INDEPENDENT_KITCHEN" if answered else "NONE",
                "value": True if answered else None,
            }, ensure_ascii=False)

    monkeypatch.setattr(user_reality_return, "_intelligence", Intelligence())
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *args: iter(["reply"]))
    monkeypatch.setattr(living_meaning_service, "form", lambda *args: None)
    monkeypatch.setattr(chat_service, "_update_profile", lambda *args, **kwargs: None)

    accepted = client.post("/api/chat/stream", json={
        "conversation_id": conversation_id,
        "message": "我问了，有独立厨房。",
        "user_reality_property_id": home.id,
    })
    assert accepted.status_code == 200
    assert "world-consequence-ready" in accepted.text
    stored = property_manager.get_scoped(home.id, conversation_id)
    assert stored.independent_kitchen is True
    assert stored.independent_kitchen_source == "USER_PROVIDED"
    assert stored.meaningful_unknown is None
    assert stored.reality_action_type is None
    assert stored.feedback_move_type is None
    response = client.get(f"/api/properties?conversation_id={conversation_id}").json()
    assert response["items"][0]["independent_kitchen"] is True

    property_manager.update_meaningful_unknown(
        home.id, conversation_id,
        question="该住所室内噪音水平如何？",
        why="影响居住判断", state_hash="unknown-noise",
    )
    property_manager.update_reality_action(
        home.id, conversation_id,
        action_type="USER_REALITY", label="实地在室内不同时段感受噪音",
        why="需要亲自观察", state_hash="action-noise",
    )
    unrelated = user_reality_return.admit(
        conversation_id, home.id, "我今天去了超市。",
    )
    assert unrelated is None
    assert property_manager.get_scoped(home.id, conversation_id).indoor_sound_observation is None

    expression = "我晚上去看了，关窗以后还是能明显听到路上的车声。"
    observed = client.post("/api/chat/stream", json={
        "conversation_id": conversation_id,
        "message": expression,
        "user_reality_property_id": home.id,
    })
    assert observed.status_code == 200
    assert "world-consequence-ready" in observed.text
    restored = property_manager.get_scoped(home.id, conversation_id)
    assert restored.indoor_sound_observation == "晚上去看了，关窗以后还是能明显听到路上的车声。"
    assert restored.indoor_sound_observation_source == "USER_PROVIDED"
    assert restored.indoor_sound_observation_unknown == "该住所室内噪音水平如何？"
    assert restored.meaningful_unknown is None
    assert restored.reality_action_type is None
    assert restored.feedback_move_type is None
    assert "dB" not in restored.indoor_sound_observation
    assert "严重" not in restored.indoor_sound_observation
    persisted = client.get(f"/api/properties?conversation_id={conversation_id}").json()
    assert next(p for p in persisted["items"] if p["id"] == home.id)["indoor_sound_observation"] == restored.indoor_sound_observation

    # Another focused property with an active Unknown tests an unrelated answer.
    other = property_manager.create(conversation_id, Property(
        title="另一住所", geographic_identity="北京市另一住所",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.33, lat=39.98,
    ))
    property_manager.update_meaningful_unknown(
        other.id, conversation_id,
        question="该住所内是否有日常使用的独立厨房？",
        why="影响日常生活安排", state_hash="other-unknown",
    )
    property_manager.update_reality_action(
        other.id, conversation_id,
        action_type="USER_REALITY", label="向房东或中介核实独立厨房",
        why="需要用户确认", state_hash="other-action",
    )
    unrelated_kitchen = user_reality_return.admit(conversation_id, other.id, "今天天气不错。")
    assert unrelated_kitchen is None
    assert property_manager.get_scoped(other.id, conversation_id).independent_kitchen is None
