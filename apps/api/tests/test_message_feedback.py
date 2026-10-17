from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.ownership import COOKIE_NAME
from app.main import app
from app.stores.runtime import conversation_store, database


def setup_conversation(owner=None):
    cid, owner = str(uuid4()), owner or str(uuid4())
    conversation_store.get_or_create(cid, owner)
    user = conversation_store.append(cid, "user", "你好")
    ai = conversation_store.append(cid, "assistant", "你好。")
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, owner)
    return client, cid, owner, user, ai


def test_feedback_create_update_cancel_and_history_recovery():
    client, cid, owner, _, ai = setup_conversation()
    path = f"/api/conversations/{cid}/messages/{ai}/feedback"
    original = client.get(f"/api/conversations/{cid}").json()["messages"]
    for value in ("POSITIVE", "POSITIVE", "NEGATIVE", None, None):
        response = client.put(path, json={"feedback": value})
        assert response.status_code == 200
        assert response.json() == {"message_id": str(ai), "feedback": value}
        restored_client = TestClient(app)
        restored_client.cookies.set(COOKIE_NAME, owner)
        messages = restored_client.get(f"/api/conversations/{cid}").json()["messages"]
        assert messages[0] == original[0]
        assert messages[1] == {**original[1], "feedback": value}
        with database.connect() as connection:
            rows = connection.execute(
                "SELECT feedback FROM conversation_message_feedback WHERE message_id = %s", (ai,),
            ).fetchall()
        assert len(rows) == (0 if value is None else 1)


def test_feedback_rejects_wrong_owner_conversation_and_non_assistant():
    client, cid, owner, user, ai = setup_conversation()
    other, other_cid, _, _, other_ai = setup_conversation()
    path = f"/api/conversations/{cid}/messages/{ai}/feedback"
    assert other.put(path, json={"feedback": "POSITIVE"}).status_code == 404
    assert TestClient(app).put(path, json={"feedback": None}).status_code == 404
    for message_id, status in ((user, 422), (other_ai, 404), (9223372036854775807, 404)):
        response = client.put(f"/api/conversations/{cid}/messages/{message_id}/feedback", json={"feedback": "POSITIVE"})
        assert response.status_code == status
    assert client.put(path, json={"feedback": "OTHER"}).status_code == 422
    assert client.put(path, json={}).status_code == 422
    assert all(m["feedback"] is None for m in client.get(f"/api/conversations/{cid}").json()["messages"])
    # The store also enforces ownership, rather than relying only on the route.
    import pytest
    with pytest.raises(LookupError):
        conversation_store.set_message_feedback(other_cid, ai, owner, "POSITIVE")
