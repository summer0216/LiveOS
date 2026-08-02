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
        conversation_id UUID PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
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
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
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
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
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
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        category TEXT NOT NULL,
        content TEXT NOT NULL,
        normalized_content TEXT NOT NULL,
        confidence DOUBLE PRECISION NOT NULL,
        evidence_record_ids_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        UNIQUE (conversation_id, category, normalized_content)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_properties_conversation ON properties(conversation_id)",
    "CREATE INDEX IF NOT EXISTS idx_records_conversation_created ON decision_records(conversation_id, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_memories_conversation_updated ON decision_memories(conversation_id, updated_at DESC)",
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
