from collections.abc import Iterator
from contextlib import contextmanager

from psycopg import Connection, connect
from psycopg.rows import DictRow, dict_row

REQUIRED_TABLES = {
    "anonymous_users",
    "conversations",
    "conversation_messages",
    "living_profiles",
    "properties",
    "decision_records",
    "decision_memories",
}

SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS anonymous_users (
        id UUID PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id UUID PRIMARY KEY,
        anonymous_user_id UUID NOT NULL REFERENCES anonymous_users(id),
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_messages (
        id BIGSERIAL PRIMARY KEY,
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        sequence INTEGER NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        UNIQUE (conversation_id, sequence)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS living_profiles (
        owner_id UUID NOT NULL REFERENCES anonymous_users(id),
        conversation_id UUID,
        work_location TEXT,
        budget INTEGER,
        commute_minutes INTEGER,
        preferred_city TEXT,
        family_size INTEGER,
        has_pet BOOLEAN,
        latest_insights_json JSONB NOT NULL,
        preference_tags_json JSONB NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS properties (
        id UUID PRIMARY KEY,
        owner_id UUID NOT NULL REFERENCES anonymous_users(id),
        conversation_id UUID,
        title TEXT,
        district TEXT,
        rent INTEGER,
        area INTEGER,
        bedrooms INTEGER,
        bathrooms INTEGER,
        commute_minutes INTEGER,
        pet_friendly BOOLEAN,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS decision_records (
        id UUID PRIMARY KEY,
        owner_id UUID NOT NULL REFERENCES anonymous_users(id),
        conversation_id UUID,
        created_at TIMESTAMPTZ NOT NULL,
        summary TEXT NOT NULL,
        best_property_id UUID NOT NULL,
        reasons_json JSONB NOT NULL,
        trade_offs_json JSONB NOT NULL,
        confidence DOUBLE PRECISION
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS decision_memories (
        id UUID PRIMARY KEY,
        owner_id UUID NOT NULL REFERENCES anonymous_users(id),
        conversation_id UUID,
        category TEXT NOT NULL,
        content TEXT NOT NULL,
        normalized_content TEXT NOT NULL,
        confidence DOUBLE PRECISION NOT NULL,
        evidence_record_ids_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
)

MIGRATION_STATEMENTS = (
    "ALTER TABLE living_profiles ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES anonymous_users(id)",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES anonymous_users(id)",
    "ALTER TABLE decision_records ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES anonymous_users(id)",
    "ALTER TABLE decision_memories ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES anonymous_users(id)",
    """
    UPDATE living_profiles AS item
    SET owner_id = conversation.anonymous_user_id
    FROM conversations AS conversation
    WHERE item.conversation_id = conversation.id AND item.owner_id IS NULL
    """,
    """
    UPDATE properties AS item
    SET owner_id = conversation.anonymous_user_id
    FROM conversations AS conversation
    WHERE item.conversation_id = conversation.id AND item.owner_id IS NULL
    """,
    """
    UPDATE decision_records AS item
    SET owner_id = conversation.anonymous_user_id
    FROM conversations AS conversation
    WHERE item.conversation_id = conversation.id AND item.owner_id IS NULL
    """,
    """
    UPDATE decision_memories AS item
    SET owner_id = conversation.anonymous_user_id
    FROM conversations AS conversation
    WHERE item.conversation_id = conversation.id AND item.owner_id IS NULL
    """,
    "ALTER TABLE living_profiles ALTER COLUMN owner_id SET NOT NULL",
    "ALTER TABLE properties ALTER COLUMN owner_id SET NOT NULL",
    "ALTER TABLE decision_records ALTER COLUMN owner_id SET NOT NULL",
    "ALTER TABLE decision_memories ALTER COLUMN owner_id SET NOT NULL",
    "ALTER TABLE living_profiles DROP CONSTRAINT IF EXISTS living_profiles_pkey",
    "ALTER TABLE living_profiles DROP CONSTRAINT IF EXISTS living_profiles_conversation_id_fkey",
    "ALTER TABLE properties DROP CONSTRAINT IF EXISTS properties_conversation_id_fkey",
    "ALTER TABLE decision_records DROP CONSTRAINT IF EXISTS decision_records_conversation_id_fkey",
    "ALTER TABLE decision_memories DROP CONSTRAINT IF EXISTS decision_memories_conversation_id_fkey",
    "ALTER TABLE living_profiles ALTER COLUMN conversation_id DROP NOT NULL",
    "ALTER TABLE properties ALTER COLUMN conversation_id DROP NOT NULL",
    "ALTER TABLE decision_records ALTER COLUMN conversation_id DROP NOT NULL",
    "ALTER TABLE decision_memories ALTER COLUMN conversation_id DROP NOT NULL",
    "ALTER TABLE decision_memories DROP CONSTRAINT IF EXISTS decision_memories_conversation_id_category_normalized_content_key",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_living_profiles_owner ON living_profiles(owner_id)",
    "CREATE INDEX IF NOT EXISTS idx_properties_owner ON properties(owner_id)",
    "CREATE INDEX IF NOT EXISTS idx_records_owner_created ON decision_records(owner_id, created_at DESC)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_memories_owner_category_content ON decision_memories(owner_id, category, normalized_content)",
    "CREATE INDEX IF NOT EXISTS idx_memories_owner_updated ON decision_memories(owner_id, updated_at DESC)",
)


class Database:
    def __init__(self, url: str) -> None:
        self._url = url

    @contextmanager
    def connect(self) -> Iterator[Connection[DictRow]]:
        with connect(self._url, row_factory=dict_row) as connection:
            yield connection

    def initialize(self) -> None:
        with self.connect() as connection:
            for statement in SCHEMA_STATEMENTS:
                connection.execute(statement)
            for statement in MIGRATION_STATEMENTS:
                connection.execute(statement)

    def health(self) -> bool:
        with self.connect() as connection:
            connection.execute("SELECT 1").fetchone()
            rows = connection.execute(
                """
                SELECT tablename AS name
                FROM pg_catalog.pg_tables
                WHERE schemaname = current_schema()
                """
            ).fetchall()
        return REQUIRED_TABLES.issubset({row["name"] for row in rows})
