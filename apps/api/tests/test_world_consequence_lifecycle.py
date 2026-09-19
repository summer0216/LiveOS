from concurrent.futures import Future, ThreadPoolExecutor
from threading import Event

from app.models.profile_analysis import ProfileAnalysis
from app.models.profile_patch import LivingProfilePatch
from app.services.chat_service import (
    STREAM_KEEP_ALIVE,
    WORLD_CONSEQUENCE_READY,
    WORLD_STATE_READY,
    ChatService,
)


def test_refinement_keeps_stream_live_then_exposes_each_durable_stage(monkeypatch):
    monkeypatch.setattr("app.services.chat_service.DISCOVERY_KEEP_ALIVE_SECONDS", 0.01)
    profile = Future()
    update_release = Event()
    discovery_release = Event()
    durable = []
    service = ChatService()

    def discovery():
        assert discovery_release.wait(2)
        durable.append("properties")

    def update(**kwargs):
        assert update_release.wait(2)
        durable.append("profile")
        kwargs["schedule_housing_discovery"](discovery)
        return ()

    monkeypatch.setattr(service, "_update_profile", update)
    monkeypatch.setattr(service, "_stream_assistant_reply", lambda *args: iter(["reply"]))
    with ThreadPoolExecutor(max_workers=2) as executor:
        stream = service._complete_stream_turn(
            "refinement", [], None, profile, executor, True, None,
        )
        try:
            assert next(stream) is WORLD_STATE_READY
            assert next(stream) is STREAM_KEEP_ALIVE
            profile.set_result(ProfileAnalysis(patch=LivingProfilePatch()))
            assert next(stream) is STREAM_KEEP_ALIVE
            update_release.set()
            event = next(stream)
            while event is STREAM_KEEP_ALIVE:
                event = next(stream)
            assert event is WORLD_CONSEQUENCE_READY
            assert durable == ["profile"]
            assert next(stream) is STREAM_KEEP_ALIVE
            discovery_release.set()
            remaining = list(stream)
            assert [item for item in remaining if item is not STREAM_KEEP_ALIVE] == [
                WORLD_CONSEQUENCE_READY, "reply",
            ]
            assert durable == ["profile", "properties"]
        finally:
            update_release.set()
            discovery_release.set()
            stream.close()
