import os

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-api-key")
os.environ.setdefault("OPENAI_BASE_URL", "http://127.0.0.1:9")
os.environ.setdefault("OPENAI_MODEL", "test-model")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://liveos:liveos_dev@127.0.0.1:5432/liveos_test",
    ),
)


@pytest.fixture(autouse=True)
def isolate_persistent_runtime_data() -> None:
    from app.stores.runtime import database

    with database.connect() as connection:
        for table in (
            "decision_memories",
            "decision_records",
            "properties",
            "living_profiles",
            "conversation_messages",
            "conversations",
        ):
            connection.execute(f"DELETE FROM {table}")
