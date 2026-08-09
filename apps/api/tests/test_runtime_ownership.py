from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from psycopg.types.json import Jsonb

from app.core.config import settings
from app.models.decision_memory import DecisionMemory, DecisionMemoryCategory
from app.models.profile import LivingProfile
from app.models.property import Property
from app.schemas.decision_record import DecisionRecord
from app.stores.database import Database
from app.stores.decision_memory_store import DecisionMemoryStore
from app.stores.persistent import (
    ConversationStore,
    DecisionRecordStore,
    ProfileStore,
    PropertyStore,
)


def database_url_for_schema(url: str, schema: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    query["options"] = f"-csearch_path={schema}"
    return urlunsplit(parts._replace(query=urlencode(query)))


def test_same_owner_shares_runtime_data_but_not_messages() -> None:
    database = Database(settings.DATABASE_URL)
    owner_id = str(uuid4())
    other_owner_id = str(uuid4())
    conversation_a = str(uuid4())
    conversation_b = str(uuid4())
    other_conversation = str(uuid4())
    conversations = ConversationStore(database)
    profiles = ProfileStore(database)
    properties = PropertyStore(database)
    records = DecisionRecordStore(database)
    memories = DecisionMemoryStore()

    conversations.get_or_create(conversation_a, owner_id)
    conversations.get_or_create(conversation_b, owner_id)
    conversations.get_or_create(other_conversation, other_owner_id)
    conversations.append(conversation_a, "user", "conversation-a-only")
    profiles.save(conversation_a, LivingProfile(budget=6000))
    property_ = properties.create(
        Property(id=str(uuid4()), conversation_id=conversation_a, title="Shared home")
    )
    record = records.save(
        DecisionRecord(
            id=str(uuid4()),
            conversation_id=conversation_a,
            created_at=datetime.now(UTC),
            summary="Shared decision",
            best_property_id=property_.id or "",
            reasons=[],
            trade_offs=[],
            confidence=0.8,
        )
    )
    timestamp = datetime.now(UTC)
    memory = memories.save(
        DecisionMemory(
            id=uuid4(),
            conversation_id=conversation_a,
            category=DecisionMemoryCategory.PRIORITY,
            content="Shared memory",
            normalized_content="shared memory",
            confidence=0.9,
            evidence_record_ids=[uuid4(), uuid4()],
            created_at=timestamp,
            updated_at=timestamp,
        )
    )

    assert profiles.get(conversation_b) == profiles.get(conversation_a)
    assert [item.id for item in properties.list(conversation_b)] == [property_.id]
    assert [item.id for item in records.list_by_conversation(conversation_b)] == [
        record.id
    ]
    assert [item.id for item in memories.list_by_conversation(conversation_b)] == [
        memory.id
    ]
    second_conversation = conversations.get(conversation_b)
    assert second_conversation is not None
    assert second_conversation.get_messages() == []

    assert profiles.get(other_conversation) is None
    assert properties.list(other_conversation) == []
    assert records.list_by_conversation(other_conversation) == []
    assert memories.list_by_conversation(other_conversation) == []

    profiles.delete(conversation_a)
    properties.delete(property_.id or "")
    records.delete_conversation(conversation_a)
    with database.connect() as connection:
        connection.execute("DELETE FROM decision_memories WHERE owner_id = %s", (owner_id,))
    conversations.delete(conversation_a)
    conversations.delete(conversation_b)
    conversations.delete(other_conversation)


def test_legacy_conversation_rows_are_backfilled_to_owner_scope() -> None:
    schema = f"runtime_ownership_{uuid4().hex}"
    root_database = Database(settings.DATABASE_URL)
    with root_database.connect() as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')

    database = Database(database_url_for_schema(settings.DATABASE_URL, schema))
    owner_id = uuid4()
    conversation_id = uuid4()
    try:
        with database.connect() as connection:
            connection.execute(
                "CREATE TABLE anonymous_users (id UUID PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL)"
            )
            connection.execute(
                """
                CREATE TABLE conversations (
                    id UUID PRIMARY KEY,
                    anonymous_user_id UUID NOT NULL REFERENCES anonymous_users(id),
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE living_profiles (
                    conversation_id UUID PRIMARY KEY REFERENCES conversations(id)
                        ON DELETE CASCADE,
                    work_location TEXT, budget INTEGER, commute_minutes INTEGER,
                    preferred_city TEXT, family_size INTEGER, has_pet BOOLEAN,
                    latest_insights_json JSONB NOT NULL,
                    preference_tags_json JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE properties (
                    id UUID PRIMARY KEY,
                    conversation_id UUID NOT NULL REFERENCES conversations(id)
                        ON DELETE CASCADE,
                    title TEXT, district TEXT, rent INTEGER, area INTEGER,
                    bedrooms INTEGER, bathrooms INTEGER, commute_minutes INTEGER,
                    pet_friendly BOOLEAN, created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE decision_records (
                    id UUID PRIMARY KEY,
                    conversation_id UUID NOT NULL REFERENCES conversations(id)
                        ON DELETE CASCADE,
                    created_at TIMESTAMPTZ NOT NULL, summary TEXT NOT NULL,
                    best_property_id UUID NOT NULL, reasons_json JSONB NOT NULL,
                    trade_offs_json JSONB NOT NULL, confidence DOUBLE PRECISION
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE decision_memories (
                    id UUID PRIMARY KEY,
                    conversation_id UUID NOT NULL REFERENCES conversations(id)
                        ON DELETE CASCADE,
                    category TEXT NOT NULL, content TEXT NOT NULL,
                    normalized_content TEXT NOT NULL,
                    confidence DOUBLE PRECISION NOT NULL,
                    evidence_record_ids_json JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    UNIQUE (conversation_id, category, normalized_content)
                )
                """
            )
            timestamp = datetime.now(UTC)
            property_id = uuid4()
            connection.execute(
                "INSERT INTO anonymous_users VALUES (%s, %s)", (owner_id, timestamp)
            )
            connection.execute(
                "INSERT INTO conversations VALUES (%s, %s, %s, %s)",
                (conversation_id, owner_id, timestamp, timestamp),
            )
            connection.execute(
                """
                INSERT INTO living_profiles VALUES (
                    %s, NULL, 6000, NULL, NULL, NULL, NULL, %s, %s, %s
                )
                """,
                (conversation_id, Jsonb([]), Jsonb({}), timestamp),
            )
            connection.execute(
                """
                INSERT INTO properties VALUES (
                    %s, %s, 'Legacy home', NULL, NULL, NULL, NULL, NULL, NULL,
                    NULL, %s, %s
                )
                """,
                (property_id, conversation_id, timestamp, timestamp),
            )
            connection.execute(
                """
                INSERT INTO decision_records VALUES (
                    %s, %s, %s, 'Legacy decision', %s, %s, %s, 0.8
                )
                """,
                (
                    uuid4(),
                    conversation_id,
                    timestamp,
                    property_id,
                    Jsonb([]),
                    Jsonb([]),
                ),
            )
            connection.execute(
                """
                INSERT INTO decision_memories VALUES (
                    %s, %s, 'priority', 'Legacy memory', 'legacy memory', 0.8,
                    %s, %s, %s
                )
                """,
                (uuid4(), conversation_id, Jsonb([]), timestamp, timestamp),
            )

        database.initialize()
        database.initialize()

        with database.connect() as connection:
            row = connection.execute(
                "SELECT owner_id, conversation_id, budget FROM living_profiles"
            ).fetchone()
            assert row is not None
            assert row["owner_id"] == owner_id
            assert row["conversation_id"] == conversation_id
            assert row["budget"] == 6000
            for table in ("properties", "decision_records", "decision_memories"):
                migrated = connection.execute(
                    f"SELECT owner_id, conversation_id FROM {table}"
                ).fetchone()
                assert migrated is not None
                assert migrated["owner_id"] == owner_id
                assert migrated["conversation_id"] == conversation_id
    finally:
        with root_database.connect() as connection:
            connection.execute(f'DROP SCHEMA "{schema}" CASCADE')


def test_duplicate_legacy_profiles_merge_without_information_loss() -> None:
    schema = f"profile_merge_{uuid4().hex}"
    root_database = Database(settings.DATABASE_URL)
    with root_database.connect() as connection:
        connection.execute(f'CREATE SCHEMA "{schema}"')

    database = Database(database_url_for_schema(settings.DATABASE_URL, schema))
    owner_id = uuid4()
    conversations = [uuid4() for _index in range(4)]
    base_time = datetime(2026, 1, 1, tzinfo=UTC)
    try:
        with database.connect() as connection:
            connection.execute(
                "CREATE TABLE anonymous_users (id UUID PRIMARY KEY, created_at TIMESTAMPTZ NOT NULL)"
            )
            connection.execute(
                """
                CREATE TABLE conversations (
                    id UUID PRIMARY KEY,
                    anonymous_user_id UUID NOT NULL REFERENCES anonymous_users(id),
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE living_profiles (
                    conversation_id UUID PRIMARY KEY REFERENCES conversations(id)
                        ON DELETE CASCADE,
                    work_location TEXT, budget INTEGER, commute_minutes INTEGER,
                    preferred_city TEXT, family_size INTEGER, has_pet BOOLEAN,
                    latest_insights_json JSONB NOT NULL,
                    preference_tags_json JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO anonymous_users VALUES (%s, %s)",
                (owner_id, base_time),
            )
            for index, conversation_id in enumerate(conversations):
                timestamp = base_time + timedelta(hours=index)
                connection.execute(
                    "INSERT INTO conversations VALUES (%s, %s, %s, %s)",
                    (conversation_id, owner_id, timestamp, timestamp),
                )

            profiles = (
                (
                    conversations[0],
                    "Old office",
                    5000,
                    None,
                    "Shenzhen",
                    None,
                    True,
                    ["old", "shared"],
                    {"preference": ["quiet", "shared"]},
                ),
                (
                    conversations[1],
                    None,
                    None,
                    30,
                    None,
                    2,
                    False,
                    ["shared", "middle"],
                    {
                        "preference": ["shared", "sunny"],
                        "lifestyle": ["pet"],
                    },
                ),
                (
                    conversations[2],
                    "New office",
                    7000,
                    None,
                    "",
                    None,
                    None,
                    ["new"],
                    {"lifestyle": ["pet", "walk"]},
                ),
                (
                    conversations[3],
                    "   ",
                    None,
                    None,
                    None,
                    None,
                    None,
                    [],
                    {},
                ),
            )
            for index, profile in enumerate(profiles):
                connection.execute(
                    """
                    INSERT INTO living_profiles VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    """,
                    (
                        *profile[:7],
                        Jsonb(profile[7]),
                        Jsonb(profile[8]),
                        base_time + timedelta(hours=index),
                    ),
                )

        database.initialize()
        with database.connect() as connection:
            first = connection.execute("SELECT * FROM living_profiles").fetchone()
        assert first is not None
        assert first["owner_id"] == owner_id
        assert first["conversation_id"] == conversations[2]
        assert first["updated_at"] == base_time + timedelta(hours=2)
        assert first["work_location"] == "New office"
        assert first["budget"] == 7000
        assert first["commute_minutes"] == 30
        assert first["preferred_city"] == "Shenzhen"
        assert first["family_size"] == 2
        assert first["has_pet"] is False
        assert first["latest_insights_json"] == ["old", "shared", "middle", "new"]
        assert first["preference_tags_json"] == {
            "preference": ["quiet", "shared", "sunny"],
            "lifestyle": ["pet", "walk"],
        }

        database.initialize()
        with database.connect() as connection:
            second = connection.execute("SELECT * FROM living_profiles").fetchone()
            count = connection.execute(
                "SELECT COUNT(*) AS count FROM living_profiles"
            ).fetchone()
        assert second == first
        assert count is not None
        assert count["count"] == 1
    finally:
        with root_database.connect() as connection:
            connection.execute(f'DROP SCHEMA "{schema}" CASCADE')
