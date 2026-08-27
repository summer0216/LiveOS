import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.ownership import COOKIE_NAME
from app.main import app
from app.models.action_progress import (
    ActionProgressStatus,
    ActionProgressUpdate,
    VerificationOutcomeStatus,
)
from app.models.decision_challenge import DecisionChallenge
from app.models.decision_feedback import DecisionRelevantFeedback
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.schemas.decision import DecisionReason, DecisionResult, DecisionTradeOff
from app.schemas.decision_record import DecisionRecord
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_action_progress import decision_action_progress_service
from app.services.decision_context_builder import decision_context_builder
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.profile_intelligence import profile_intelligence
from app.services.profile_manager import profile_manager
from app.stores.runtime import decision_action_state_store
from tests.ids import uuid_for


def analysis_json(
    *,
    work_location: str | None = None,
    preferred_city: str | None = None,
    commute_minutes: int | None = None,
    feedback: dict[str, object] | None = None,
    challenge: dict[str, object] | None = None,
) -> str:
    return json.dumps(
        {
            "work_location": work_location,
            "budget": None,
            "commute_minutes": commute_minutes,
            "preferred_city": preferred_city,
            "family_size": None,
            "has_pet": None,
            "clear_fields": [],
            "decision_relevant_feedback": feedback
            or {
                "relevant": False,
                "observation": None,
                "judgment": None,
                "observed_commute_minutes": None,
            },
            "decision_challenge": challenge
            or {
                "relevant": False,
                "kind": None,
                "subject": None,
                "statement": None,
                "target_property_id": None,
            },
            "action_progress_update": {
                "relevant": False,
                "status": None,
            },
            "verification_outcome_update": {
                "relevant": False,
                "status": None,
                "evidence": [],
            },
        },
        ensure_ascii=False,
    )


def save_ready(
    conversation_id: str,
    *,
    owner_id: str | None = None,
    property_id: str | None = None,
    decision_text: str = "当前方案可行。",
    next_text: str | None = "核实房源城市。",
) -> DecisionRecord:
    if owner_id is None:
        conversation_manager.get_or_create(conversation_id)
    else:
        conversation_manager.get_or_create(conversation_id, owner_id)
    summary = decision_text
    if next_text is not None:
        summary += f" 下一步：{next_text}"
    return decision_record_service.save(
        conversation_id,
        DecisionResult(
            status="ready",
            summary=summary,
            best_property_id=property_id or str(uuid4()),
            reasons=[DecisionReason(title="判断", description="当前判断依据。")],
            trade_offs=[
                DecisionTradeOff(title="取舍", description="当前取舍依据。")
            ],
            confidence=0.8,
        ),
    )


@pytest.mark.parametrize(
    ("message", "status", "field", "value"),
    (
        (
            "确认了，就在深圳南山。",
            VerificationOutcomeStatus.CONFIRMED,
            "city",
            "深圳南山",
        ),
        (
            "确认过了，不在深圳，在成都。",
            VerificationOutcomeStatus.DISCONFIRMED,
            "city",
            "成都",
        ),
        (
            "问过了，中介也确认不了。",
            VerificationOutcomeStatus.INCONCLUSIVE,
            "statement",
            "问过了，中介也确认不了。",
        ),
    ),
)
def test_explicit_verification_outcome_implies_completed(
    message: str,
    status: VerificationOutcomeStatus,
    field: str,
    value: str,
) -> None:
    analysis = profile_intelligence._build_analysis(analysis_json(), message)

    assert analysis.action_progress_update.status == ActionProgressStatus.COMPLETED
    assert analysis.verification_outcome_update.status == status
    assert analysis.verification_outcome_update.evidence[0].field == field
    assert analysis.verification_outcome_update.evidence[0].value == value
    assert (
        analysis.verification_outcome_update.evidence[0].provenance
        == "USER_REPORTED"
    )


def test_disconfirmed_city_does_not_mutate_profile_preference() -> None:
    analysis = profile_intelligence._build_analysis(
        analysis_json(preferred_city="成都"),
        "确认过了，不在深圳，在成都。",
    )

    assert analysis.verification_outcome_update.status == (
        VerificationOutcomeStatus.DISCONFIRMED
    )
    assert analysis.patch.preferred_city is None
    assert analysis.patch.work_location is None


def test_inconclusive_outcome_blocks_stale_profile_patch() -> None:
    analysis = profile_intelligence._build_analysis(
        analysis_json(work_location="深圳南山", preferred_city="深圳"),
        "问过了，中介也确认不了。",
    )

    assert analysis.verification_outcome_update.status == (
        VerificationOutcomeStatus.INCONCLUSIVE
    )
    assert analysis.patch.work_location is None
    assert analysis.patch.preferred_city is None


def test_completed_only_and_ambiguous_messages_do_not_create_outcome() -> None:
    completed = profile_intelligence._build_analysis(
        analysis_json(),
        "我已经查过了。",
    )
    ambiguous = profile_intelligence._build_analysis(
        analysis_json(),
        "好像是在深圳。",
    )
    ordinary = profile_intelligence._build_analysis(
        analysis_json(),
        "好的，我知道了。",
    )

    assert completed.action_progress_update.status == ActionProgressStatus.COMPLETED
    assert completed.verification_outcome_update.relevant is False
    assert ambiguous.verification_outcome_update.relevant is False
    assert ordinary.action_progress_update.relevant is False
    assert ordinary.verification_outcome_update.relevant is False


def test_outcome_feedback_profile_and_challenge_semantics_coexist() -> None:
    feedback = {
        "relevant": True,
        "observation": "实际通勤80分钟，无法接受。",
        "judgment": "unacceptable",
        "observed_commute_minutes": 80,
    }
    challenge = {
        "relevant": True,
        "kind": "DIRECT",
        "subject": "当前推荐",
        "statement": "我也不认同之前的推荐。",
        "target_property_id": None,
    }
    outcome_feedback = profile_intelligence._build_analysis(
        analysis_json(feedback=feedback),
        "我试过了，实际80分钟，我接受不了。",
    )
    outcome_profile = profile_intelligence._build_analysis(
        analysis_json(commute_minutes=40, feedback=feedback),
        "我试过了，实际80分钟，以后最多只能接受40分钟。",
    )
    outcome_challenge = profile_intelligence._build_analysis(
        analysis_json(challenge=challenge),
        "确认过了，这个信息确实不对，我也不认同之前的推荐。",
    )

    assert outcome_feedback.verification_outcome_update.relevant is True
    assert outcome_feedback.decision_feedback.observed_commute_minutes == 80
    assert outcome_profile.verification_outcome_update.evidence[0].value == 80
    assert outcome_profile.patch.commute_minutes == 40
    assert outcome_challenge.verification_outcome_update.relevant is True
    assert outcome_challenge.decision_challenge.kind == "DIRECT"


@pytest.mark.parametrize(
    "case",
    ("outcome", "feedback", "profile", "challenge", "all"),
)
def test_outcome_uses_existing_exactly_once_decision_boundary(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
) -> None:
    conversation_id = uuid_for(f"verification-exactly-once-{case}")
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)
    base = profile_intelligence._build_analysis(
        analysis_json(),
        "确认了，就在深圳南山。",
    )
    analysis = base.model_copy(
        update={
            "patch": (
                LivingProfilePatch(commute_minutes=40)
                if case in {"profile", "all"}
                else LivingProfilePatch()
            ),
            "decision_feedback": (
                DecisionRelevantFeedback(
                    relevant=True,
                    observation="实测通勤80分钟，无法接受。",
                    judgment="unacceptable",
                    observed_commute_minutes=80,
                )
                if case in {"feedback", "all"}
                else base.decision_feedback
            ),
            "decision_challenge": (
                DecisionChallenge(
                    relevant=True,
                    kind="DIRECT",
                    statement="我仍然不认同当前推荐。",
                )
                if case in {"challenge", "all"}
                else base.decision_challenge
            ),
        }
    )
    if analysis.patch.commute_minutes is not None:
        profile_manager.merge(
            conversation_id,
            LivingProfilePatch(commute_minutes=65),
            [],
        )
    monkeypatch.setattr(profile_intelligence, "analyze", lambda _history: analysis)

    causes = chat_service._update_profile(conversation_id, [])
    current = decision_action_progress_service.resolve_current(conversation_id)

    assert int(bool(causes)) == 1
    assert sum(cause.source == "VERIFICATION_OUTCOME" for cause in causes) == 1
    assert current is not None
    assert current.status == ActionProgressStatus.COMPLETED
    assert current.outcome_status == VerificationOutcomeStatus.CONFIRMED


def test_progress_only_still_has_zero_decision_causes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    conversation_id = uuid_for("verification-progress-only")
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)
    analysis = ProfileAnalysis(
        patch=LivingProfilePatch(),
        action_progress_update=ActionProgressUpdate(
            relevant=True,
            status=ActionProgressStatus.COMPLETED,
        ),
    )

    monkeypatch.setattr(profile_intelligence, "analyze", lambda _history: analysis)

    causes = chat_service._update_profile(conversation_id, [])
    current_after = decision_action_progress_service.resolve_current(conversation_id)

    assert causes == ()
    assert current_after is not None
    assert current_after.status == ActionProgressStatus.COMPLETED
    assert current_after.outcome_status is None


def test_outcome_correction_equivalent_ready_and_new_action_isolation() -> None:
    conversation_id = uuid_for("verification-continuity")
    property_id = str(uuid4())
    first = save_ready(conversation_id, property_id=property_id)
    decision_action_progress_service.reconcile_ready_record(first)
    inconclusive = profile_intelligence._build_analysis(
        analysis_json(),
        "问过了，中介也确认不了。",
    )
    decision_action_progress_service.apply_update(
        conversation_id,
        inconclusive.action_progress_update,
        inconclusive.verification_outcome_update,
    )
    confirmed = profile_intelligence._build_analysis(
        analysis_json(),
        "确认了，就在深圳南山。",
    )
    corrected = decision_action_progress_service.apply_update(
        conversation_id,
        confirmed.action_progress_update,
        confirmed.verification_outcome_update,
    )
    equivalent = save_ready(
        conversation_id,
        property_id=property_id,
        decision_text="判断解释已经更新，但行动方向不变。",
    )
    preserved = decision_action_progress_service.reconcile_ready_record(equivalent)

    assert corrected is not None
    assert preserved is not None
    assert preserved.action_id == corrected.action_id
    assert preserved.outcome_status == VerificationOutcomeStatus.CONFIRMED
    assert preserved.verification_evidence == corrected.verification_evidence

    changed = save_ready(
        conversation_id,
        property_id=property_id,
        decision_text="新的判断不可行。",
        next_text="比较另一套具体房源。",
    )
    reset = decision_action_progress_service.reconcile_ready_record(changed)

    assert reset is not None
    assert reset.action_id != preserved.action_id
    assert reset.status is None
    assert reset.outcome_status is None
    assert reset.verification_evidence == ()


def test_same_next_text_under_different_decision_does_not_leak_outcome() -> None:
    conversation_id = uuid_for("verification-same-next")
    first = save_ready(conversation_id, property_id=str(uuid4()))
    decision_action_progress_service.reconcile_ready_record(first)
    confirmed = profile_intelligence._build_analysis(
        analysis_json(),
        "确认了，就在深圳南山。",
    )
    current = decision_action_progress_service.apply_update(
        conversation_id,
        confirmed.action_progress_update,
        confirmed.verification_outcome_update,
    )
    second = save_ready(conversation_id, property_id=str(uuid4()))
    isolated = decision_action_progress_service.reconcile_ready_record(second)

    assert current is not None
    assert isolated is not None
    assert isolated.action_id != current.action_id
    assert isolated.outcome_status is None
    assert isolated.verification_evidence == ()


def test_decision_context_and_resume_restore_persisted_outcome_read_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_id = str(uuid4())
    conversation_id = str(uuid4())
    record = save_ready(conversation_id, owner_id=owner_id)
    decision_action_progress_service.reconcile_ready_record(record)
    confirmed = profile_intelligence._build_analysis(
        analysis_json(),
        "确认了，就在深圳南山。",
    )
    current = decision_action_progress_service.apply_update(
        conversation_id,
        confirmed.action_progress_update,
        confirmed.verification_outcome_update,
    )
    before = decision_action_state_store.get(conversation_id)

    context = decision_context_builder.build(conversation_id)
    assert context.current_action == current

    monkeypatch.setattr(
        profile_intelligence,
        "analyze",
        lambda _history: pytest.fail("Resume must not call Profile Intelligence."),
    )
    monkeypatch.setattr(
        decision_service,
        "generate",
        lambda _conversation_id: pytest.fail("Resume must not generate Decision."),
    )
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, owner_id)
    response = client.get("/api/resume", params={"conversation_id": conversation_id})
    after = decision_action_state_store.get(conversation_id)

    assert response.status_code == 200
    payload = response.json()["action_progress"]
    assert payload["action_id"] == current.action_id
    assert payload["status"] == "COMPLETED"
    assert payload["outcome_status"] == "CONFIRMED"
    assert payload["verification_evidence"][0]["provenance"] == "USER_REPORTED"
    assert after == before


def test_legacy_no_next_has_no_synthetic_verification_state() -> None:
    conversation_id = uuid_for("verification-legacy")
    record = save_ready(conversation_id, next_text=None)

    assert decision_action_progress_service.resolve_for_record(record) is None
