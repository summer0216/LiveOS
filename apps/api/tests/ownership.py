from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.ownership import COOKIE_NAME
from app.services.conversation_manager import conversation_manager


def create_owned_conversation(client: TestClient, conversation_id: str) -> None:
    """Bind a clean test conversation to the anonymous user in ``client``."""
    user_id = client.cookies.get(COOKIE_NAME)
    if user_id is None:
        user_id = str(uuid4())
        client.cookies.set(COOKIE_NAME, user_id)

    conversation_manager.delete(conversation_id)
    conversation_manager.get_or_create(conversation_id, user_id)
