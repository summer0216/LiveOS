from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import chat as chat_api
from app.api.ownership import COOKIE_NAME
from app.main import app
from app.services.conversation_manager import conversation_manager
from app.stores.runtime import conversation_store, database


def test_history_preserves_database_message_identity_and_creation_time():
    cid, owner = str(uuid4()), str(uuid4())
    conversation_store.get_or_create(cid, owner)
    ids = [conversation_store.append(cid, role, text) for role, text in (
        ("user", "重复表达"), ("assistant", "重复回复"),
        ("user", "重复表达"), ("assistant", "重复回复"),
    )]
    timestamp = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    with database.connect() as connection:
        connection.execute(
            "UPDATE conversation_messages SET created_at = %s WHERE conversation_id = %s",
            (timestamp, cid),
        )
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, owner)
    first = client.get(f"/api/conversations/{cid}")
    assert first.status_code == 200
    messages = first.json()["messages"]
    assert [item["id"] for item in messages] == [str(id_) for id_ in ids]
    assert [item["role"] for item in messages] == ["user", "assistant", "user", "assistant"]
    assert all(datetime.fromisoformat(item["created_at"]) == timestamp for item in messages)
    restored = conversation_store.get(cid).get_messages()
    assert [item.id for item in restored] == ids
    assert all(item.created_at == timestamp for item in restored)
    assert client.get(f"/api/conversations/{cid}").json() == first.json()
    assert TestClient(app).get(f"/api/conversations/{cid}").status_code == 404


def test_completed_stream_is_available_as_persisted_history(monkeypatch):
    cid = str(uuid4())

    def stream(**kwargs):
        conversation_manager.append_user_message(cid, kwargs["message"])
        yield "第一段"
        yield "第二段"
        conversation_manager.append_assistant_message(cid, "第一段第二段")

    monkeypatch.setattr(chat_api.chat_service, "chat_stream", stream)
    client = TestClient(app)
    response = client.post("/api/chat/stream", json={"conversation_id": cid, "message": "测试"})
    assert response.status_code == 200
    history = client.get(f"/api/conversations/{cid}")
    assert history.status_code == 200
    messages = history.json()["messages"]
    assert [item["content"] for item in messages] == ["测试", "第一段第二段"]
    assert len({item["id"] for item in messages}) == 2
    assert all(item["created_at"] for item in messages)
    assert client.get(f"/api/conversations/{cid}").json() == history.json()
