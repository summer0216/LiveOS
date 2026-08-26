import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.ownership import COOKIE_NAME
from app.core.config import settings
from app.main import app
from app.models.action_progress import (
    ActionProgressStatus,
    ActionProgressUpdate,
)
from app.models.decision_challenge import DecisionChallenge
from app.models.decision_feedback import DecisionRelevantFeedback
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.schemas.decision import DecisionReason, DecisionResult, DecisionTradeOff
from app.schemas.decision_record import DecisionRecord
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_action_progress import (
    decision_action_progress_service,
    describe_logical_action,
)
from app.services.decision_record_service import decision_record_service
from app.services.decision_service import decision_service
from app.services.profile_intelligence import profile_intelligence
from app.services.profile_manager import profile_manager
from app.stores.database import Database
from app.stores.persistent import DecisionActionStateStore
from app.stores.runtime import decision_action_state_store
from tests.ids import uuid_for


def no_challenge() -> dict[str, object]:
    return {
        "relevant": False,
        "kind": None,
        "subject": None,
        "statement": None,
        "target_property_id": None,
    }


def no_feedback() -> dict[str, object]:
    return {
        "relevant": False,
        "observation": None,
        "judgment": None,
        "observed_commute_minutes": None,
    }


def analysis_json(
    *,
    progress_status: str | None,
    feedback: dict[str, object] | None = None,
    challenge: dict[str, object] | None = None,
    commute_minutes: int | None = None,
) -> str:
    return json.dumps(
        {
            "work_location": None,
            "budget": None,
            "commute_minutes": commute_minutes,
            "preferred_city": None,
            "family_size": None,
            "has_pet": None,
            "clear_fields": [],
            "decision_relevant_feedback": feedback or no_feedback(),
            "decision_challenge": challenge or no_challenge(),
            "action_progress_update": {
                "relevant": progress_status is not None,
                "status": progress_status,
            },
        },
        ensure_ascii=False,
    )


def save_ready(
    conversation_id: str,
    *,
    owner_id: str | None = None,
    label: str = "A",
    next_text: str | None = "验证工作日高峰通勤。",
    property_id: str | None = None,
    decision_text: str | None = None,
) -> DecisionRecord:
    if owner_id is None:
        conversation_manager.get_or_create(conversation_id)
    else:
        conversation_manager.get_or_create(conversation_id, owner_id)
    summary = decision_text or f"{label}方案可行。"
    if next_text is not None:
        summary += f" 下一步：{next_text}"
    return decision_record_service.save(
        conversation_id,
        DecisionResult(
            status="ready",
            summary=summary,
            best_property_id=property_id or str(uuid4()),
            reasons=[DecisionReason(title="判断", description=f"{label}依据")],
            trade_offs=[DecisionTradeOff(title="取舍", description=f"{label}取舍")],
            confidence=0.8,
        ),
    )


@pytest.mark.parametrize(
    ("message", "status"),
    (
        ("我明天早上去试一下。", ActionProgressStatus.PLANNED),
        ("还没去试。", ActionProgressStatus.NOT_STARTED),
        ("我今天已经试过了。", ActionProgressStatus.COMPLETED),
        ("这个我不打算验证了。", ActionProgressStatus.ABANDONED),
    ),
)
def test_explicit_action_progress_is_bounded(
    message: str,
    status: ActionProgressStatus,
) -> None:
    analysis = profile_intelligence._build_analysis(
        analysis_json(progress_status=status.value),
        message,
    )

    assert analysis.action_progress_update == ActionProgressUpdate(
        relevant=True,
        status=status,
    )
    assert analysis.patch == LivingProfilePatch()
    assert analysis.decision_feedback.relevant is False
    assert analysis.decision_challenge.relevant is False


def test_ambiguous_intent_is_no_change_and_correction_wins() -> None:
    ambiguous = profile_intelligence._build_analysis(
        analysis_json(progress_status="PLANNED"),
        "也许可以去看看。",
    )
    correction = profile_intelligence._build_analysis(
        analysis_json(progress_status="NOT_STARTED"),
        "我刚才说错了，其实还没去。",
    )

    assert ambiguous.action_progress_update.relevant is False
    assert correction.action_progress_update.status == ActionProgressStatus.NOT_STARTED


def test_completed_feedback_profile_and_challenge_remain_independent() -> None:
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
        "statement": "我还是不认同你的推荐。",
        "target_property_id": None,
    }
    completed_feedback = profile_intelligence._build_analysis(
        analysis_json(progress_status="COMPLETED", feedback=feedback),
        "我已经试过了，实际80分钟，我接受不了。",
    )
    completed_profile = profile_intelligence._build_analysis(
        analysis_json(progress_status="COMPLETED", commute_minutes=40),
        "我已经试过通勤了，以后最多只能接受40分钟。",
    )
    completed_challenge = profile_intelligence._build_analysis(
        analysis_json(progress_status="COMPLETED", challenge=challenge),
        "我已经看过这个房子了，但我还是不认同你的推荐。",
    )

    assert completed_feedback.action_progress_update.status == ActionProgressStatus.COMPLETED
    assert completed_feedback.decision_feedback.observed_commute_minutes == 80
    assert completed_feedback.patch.commute_minutes is None
    assert completed_profile.action_progress_update.status == ActionProgressStatus.COMPLETED
    assert completed_profile.patch.commute_minutes == 40
    assert completed_challenge.action_progress_update.status == ActionProgressStatus.COMPLETED
    assert completed_challenge.decision_challenge.kind == "DIRECT"


@pytest.mark.parametrize(
    "status",
    tuple(ActionProgressStatus),
)
def test_progress_only_persists_without_decision_cause_or_request(
    monkeypatch: pytest.MonkeyPatch,
    status: ActionProgressStatus,
) -> None:
    conversation_id = uuid_for(f"action-progress-only-{status.value}")
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)
    analysis = ProfileAnalysis(
        patch=LivingProfilePatch(),
        action_progress_update=ActionProgressUpdate(relevant=True, status=status),
    )
    decision_requests = 0

    monkeypatch.setattr(profile_intelligence, "analyze", lambda _history: analysis)

    def unexpected_decision(_conversation_id: str) -> None:
        nonlocal decision_requests
        decision_requests += 1

    monkeypatch.setattr(decision_service, "generate", unexpected_decision)

    causes = chat_service._update_profile(conversation_id, [])
    current = decision_action_progress_service.resolve_current(conversation_id)

    assert causes == ()
    assert decision_requests == 0
    assert current is not None
    assert current.status == status


@pytest.mark.parametrize(
    ("case", "analysis", "expected_sources"),
    (
        (
            "feedback",
            ProfileAnalysis(
                patch=LivingProfilePatch(),
                decision_feedback=DecisionRelevantFeedback(
                    relevant=True,
                    observation="实测通勤80分钟，无法接受。",
                    judgment="unacceptable",
                    observed_commute_minutes=80,
                ),
                action_progress_update=ActionProgressUpdate(
                    relevant=True,
                    status=ActionProgressStatus.COMPLETED,
                ),
            ),
            ["DECISION_RELEVANT_FEEDBACK"],
        ),
        (
            "profile",
            ProfileAnalysis(
                patch=LivingProfilePatch(commute_minutes=40),
                action_progress_update=ActionProgressUpdate(
                    relevant=True,
                    status=ActionProgressStatus.COMPLETED,
                ),
            ),
            ["PROFILE_MUTATION"],
        ),
        (
            "challenge",
            ProfileAnalysis(
                patch=LivingProfilePatch(),
                decision_challenge=DecisionChallenge(
                    relevant=True,
                    kind="DIRECT",
                    statement="我仍然不认同当前推荐。",
                ),
                action_progress_update=ActionProgressUpdate(
                    relevant=True,
                    status=ActionProgressStatus.COMPLETED,
                ),
            ),
            ["DECISION_CHALLENGE"],
        ),
        (
            "all",
            ProfileAnalysis(
                patch=LivingProfilePatch(commute_minutes=40),
                decision_feedback=DecisionRelevantFeedback(
                    relevant=True,
                    observation="实测通勤80分钟，无法接受。",
                    judgment="unacceptable",
                    observed_commute_minutes=80,
                ),
                decision_challenge=DecisionChallenge(
                    relevant=True,
                    kind="DIRECT",
                    statement="我仍然不认同当前推荐。",
                ),
                action_progress_update=ActionProgressUpdate(
                    relevant=True,
                    status=ActionProgressStatus.COMPLETED,
                ),
            ),
            [
                "PROFILE_MUTATION",
                "DECISION_RELEVANT_FEEDBACK",
                "DECISION_CHALLENGE",
            ],
        ),
    ),
)
def test_progress_coexists_with_existing_exactly_once_causes(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    analysis: ProfileAnalysis,
    expected_sources: list[str],
) -> None:
    conversation_id = uuid_for(f"action-progress-multi-{case}")
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)
    if analysis.patch.commute_minutes is not None:
        profile_manager.merge(
            conversation_id,
            LivingProfilePatch(commute_minutes=65),
            [],
        )
    monkeypatch.setattr(profile_intelligence, "analyze", lambda _history: analysis)

    causes = chat_service._update_profile(conversation_id, [])
    current = decision_action_progress_service.resolve_current(conversation_id)

    assert [cause.source for cause in causes] == expected_sources
    assert int(bool(causes)) == 1
    assert current is not None
    assert current.status == ActionProgressStatus.COMPLETED


def test_initial_unknown_equivalent_ready_and_new_next_transition() -> None:
    conversation_id = uuid_for("action-progress-continuity")
    property_id = str(uuid4())
    first = save_ready(conversation_id, property_id=property_id)
    initial = decision_action_progress_service.reconcile_ready_record(first)
    assert initial is not None
    assert initial.status is None

    planned = decision_action_progress_service.apply_update(
        conversation_id,
        ActionProgressUpdate(relevant=True, status=ActionProgressStatus.PLANNED),
    )
    equivalent = save_ready(conversation_id, property_id=property_id)
    preserved = decision_action_progress_service.reconcile_ready_record(equivalent)

    assert planned is not None
    assert preserved is not None
    assert preserved.action_id == planned.action_id
    assert preserved.status == ActionProgressStatus.PLANNED

    changed = save_ready(
        conversation_id,
        label="B",
        property_id=property_id,
        next_text="比较两套具体房源。",
    )
    reset = decision_action_progress_service.reconcile_ready_record(changed)

    assert reset is not None
    assert reset.action_id != planned.action_id
    assert reset.status is None


def test_same_next_text_alone_does_not_preserve_progress() -> None:
    conversation_id = uuid_for("action-progress-same-text")
    first = save_ready(conversation_id, property_id=str(uuid4()))
    first_progress = decision_action_progress_service.reconcile_ready_record(first)
    decision_action_progress_service.apply_update(
        conversation_id,
        ActionProgressUpdate(relevant=True, status=ActionProgressStatus.COMPLETED),
    )
    second = save_ready(
        conversation_id,
        label="B",
        property_id=str(uuid4()),
        next_text="验证工作日高峰通勤。",
    )
    second_progress = decision_action_progress_service.reconcile_ready_record(second)

    assert first_progress is not None
    assert second_progress is not None
    assert second_progress.action_id != first_progress.action_id
    assert second_progress.status is None


def test_legacy_next_has_no_action_progress() -> None:
    conversation_id = uuid_for("action-progress-legacy")
    record = save_ready(conversation_id, next_text=None)

    assert describe_logical_action(record) is None
    assert decision_action_progress_service.resolve_for_record(record) is None


def test_resume_restores_progress_without_writes_or_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_id = str(uuid4())
    conversation_id = str(uuid4())
    record = save_ready(conversation_id, owner_id=owner_id)
    decision_action_progress_service.reconcile_ready_record(record)
    decision_action_progress_service.apply_update(
        conversation_id,
        ActionProgressUpdate(relevant=True, status=ActionProgressStatus.PLANNED),
    )
    before = decision_action_state_store.get(conversation_id)
    assert before is not None

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
    assert response.json()["action_progress"]["status"] == "PLANNED"
    assert after == before


def test_action_progress_survives_database_reconnect() -> None:
    conversation_id = uuid_for("action-progress-reconnect")
    record = save_ready(conversation_id)
    decision_action_progress_service.reconcile_ready_record(record)
    decision_action_progress_service.apply_update(
        conversation_id,
        ActionProgressUpdate(relevant=True, status=ActionProgressStatus.PLANNED),
    )

    reconnected_database = Database(settings.DATABASE_URL)
    reconnected_database.initialize()
    persisted = DecisionActionStateStore(reconnected_database).get(conversation_id)

    assert persisted is not None
    assert persisted.status == ActionProgressStatus.PLANNED


def test_owner_and_conversation_action_progress_isolation() -> None:
    owner_a = str(uuid4())
    owner_b = str(uuid4())
    conversation_a = str(uuid4())
    conversation_b = str(uuid4())
    conversation_other = str(uuid4())
    record_a = save_ready(conversation_a, owner_id=owner_a, label="A")
    record_b = save_ready(conversation_b, owner_id=owner_a, label="B")
    record_other = save_ready(conversation_other, owner_id=owner_b, label="OTHER")
    for record, status in (
        (record_a, ActionProgressStatus.PLANNED),
        (record_b, ActionProgressStatus.COMPLETED),
        (record_other, ActionProgressStatus.ABANDONED),
    ):
        decision_action_progress_service.reconcile_ready_record(record)
        decision_action_progress_service.apply_update(
            record.conversation_id,
            ActionProgressUpdate(relevant=True, status=status),
        )

    client_a = TestClient(app)
    client_a.cookies.set(COOKIE_NAME, owner_a)
    client_b = TestClient(app)
    client_b.cookies.set(COOKIE_NAME, owner_b)

    response_a = client_a.get(
        "/api/resume", params={"conversation_id": conversation_a}
    )
    response_b = client_a.get(
        "/api/resume", params={"conversation_id": conversation_b}
    )
    forbidden = client_a.get(
        "/api/resume", params={"conversation_id": conversation_other}
    )
    other = client_b.get(
        "/api/resume", params={"conversation_id": conversation_other}
    )

    assert response_a.json()["action_progress"]["status"] == "PLANNED"
    assert response_b.json()["action_progress"]["status"] == "COMPLETED"
    assert forbidden.status_code == 404
    assert other.json()["action_progress"]["status"] == "ABANDONED"
