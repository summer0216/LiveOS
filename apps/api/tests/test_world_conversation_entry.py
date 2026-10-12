from fastapi.testclient import TestClient

from app.api.ownership import COOKIE_NAME
from app.main import app
from app.models.decision_geography import DecisionGeography
from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.models.property import GeographicPrecision, GeographicStatus, Property
from app.services.chat_service import chat_service
from app.services.conversation_manager import conversation_manager
from app.services.decision_signal_intelligence import decision_signal_intelligence
from app.services.profile_intelligence import profile_intelligence
from app.services.property_manager import property_manager
from app.services.user_reality_return import (
    PropertyExpressionResolution,
    user_reality_return,
)
from tests.ids import uuid_for


def test_second_and_third_stream_turns_keep_current_conversation_and_grounded_subject(
    monkeypatch,
) -> None:
    conversation_id = uuid_for("world-entry-conversation")
    owner_id = uuid_for("world-entry-owner")
    conversation_manager.get_or_create(conversation_id, owner_id)
    conversation_manager.append_user_message(conversation_id, "我住在龙湖时代天街")
    home = property_manager.create(conversation_id, Property(
        title="龙湖时代天街",
        geographic_status=GeographicStatus.GROUNDED,
        geographic_precision=GeographicPrecision.PLACE,
        geographic_identity="测试 Grounded Place",
        lng=104,
        lat=31,
    ))
    observed = []

    def analyze(history, properties):
        assert history[0].content == "我住在龙湖时代天街"
        assert [property_.id for property_ in properties] == [home.id]
        assert properties[0].geographic_status == GeographicStatus.GROUNDED
        observed.append(history[-1].content)
        return ProfileAnalysis(patch=LivingProfilePatch())

    # Keep model output neutral; exercise the existing API, stream orchestration,
    # authoritative Property reads and PostgreSQL Conversation persistence.
    monkeypatch.setattr(profile_intelligence, "analyze", analyze)
    monkeypatch.setattr(decision_signal_intelligence, "analyze", lambda _message: DecisionGeography())
    monkeypatch.setattr(chat_service, "_update_profile", lambda **_kwargs: ())
    monkeypatch.setattr(
        user_reality_return, "resolve_expression",
        lambda *_args, **_kwargs: PropertyExpressionResolution(),
    )
    monkeypatch.setattr(chat_service, "_stream_assistant_reply", lambda *_args: iter(["收到"]))
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, owner_id)

    for message in ("附近吃饭方便吗？", "交通呢？"):
        response = client.post("/api/chat/stream", json={
            "conversation_id": conversation_id,
            "message": message,
        })
        assert response.status_code == 200
        assert "event: world-consequence-ready" in response.text
        assert 'data: "收到"' in response.text
        stored = property_manager.get_scoped(home.id, conversation_id)
        assert stored is not None
        assert stored.geographic_status == GeographicStatus.GROUNDED
        assert (stored.lng, stored.lat) == (home.lng, home.lat)
        assert conversation_manager.owner_id(conversation_id) == owner_id

    assert observed == ["附近吃饭方便吗？", "交通呢？"]
    assert [message.content for message in conversation_manager.get_history(conversation_id)] == [
        "我住在龙湖时代天街", "附近吃饭方便吗？", "交通呢？",
    ]
