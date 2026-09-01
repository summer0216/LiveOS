from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from psycopg import Connection, connect
from psycopg.rows import DictRow, dict_row
from psycopg.types.json import Jsonb

REQUIRED_TABLES = {
    "anonymous_users",
    "conversations",
    "conversation_messages",
    "living_profiles",
    "properties",
    "decision_records",
    "decision_action_states",
    "latest_verified_actions",
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
        confidence DOUBLE PRECISION,
        decision_gap TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS decision_action_states (
        id UUID PRIMARY KEY,
        owner_id UUID NOT NULL REFERENCES anonymous_users(id),
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        decision_record_id UUID NOT NULL,
        action_key TEXT NOT NULL,
        next_text TEXT NOT NULL,
        status TEXT CHECK (
            status IS NULL OR status IN (
                'NOT_STARTED', 'PLANNED', 'COMPLETED', 'ABANDONED'
            )
        ),
        outcome_status TEXT CHECK (
            outcome_status IS NULL OR outcome_status IN (
                'CONFIRMED', 'DISCONFIRMED', 'INCONCLUSIVE'
            )
        ),
        verification_evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        UNIQUE (owner_id, conversation_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS latest_verified_actions (
        owner_id UUID NOT NULL REFERENCES anonymous_users(id),
        conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        action_id UUID NOT NULL,
        decision_record_id UUID NOT NULL,
        action_key TEXT NOT NULL,
        next_text TEXT NOT NULL,
        status TEXT NOT NULL CHECK (status = 'COMPLETED'),
        outcome_status TEXT NOT NULL CHECK (
            outcome_status IN ('CONFIRMED', 'DISCONFIRMED', 'INCONCLUSIVE')
        ),
        verification_evidence_json JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL,
        PRIMARY KEY (owner_id, conversation_id)
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
        source_action_id UUID,
        source_action_key TEXT,
        source_outcome_status TEXT CHECK (
            source_outcome_status IS NULL OR source_outcome_status IN (
                'CONFIRMED', 'DISCONFIRMED', 'INCONCLUSIVE'
            )
        ),
        source_decision_record_id UUID,
        created_at TIMESTAMPTZ NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL
    )
    """,
)

OWNERSHIP_BACKFILL_STATEMENTS = (
    "ALTER TABLE decision_action_states ADD COLUMN IF NOT EXISTS outcome_status TEXT",
    "ALTER TABLE decision_action_states ADD COLUMN IF NOT EXISTS verification_evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb",
    "ALTER TABLE decision_action_states DROP CONSTRAINT IF EXISTS decision_action_states_outcome_status_check",
    "ALTER TABLE decision_action_states ADD CONSTRAINT decision_action_states_outcome_status_check CHECK (outcome_status IS NULL OR outcome_status IN ('CONFIRMED', 'DISCONFIRMED', 'INCONCLUSIVE'))",
    "ALTER TABLE living_profiles ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES anonymous_users(id)",
    "ALTER TABLE properties ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES anonymous_users(id)",
    "ALTER TABLE decision_records ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES anonymous_users(id)",
    "ALTER TABLE decision_records ADD COLUMN IF NOT EXISTS decision_gap TEXT",
    "ALTER TABLE decision_memories ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES anonymous_users(id)",
    "ALTER TABLE decision_memories ADD COLUMN IF NOT EXISTS source_action_id UUID",
    "ALTER TABLE decision_memories ADD COLUMN IF NOT EXISTS source_action_key TEXT",
    "ALTER TABLE decision_memories ADD COLUMN IF NOT EXISTS source_outcome_status TEXT",
    "ALTER TABLE decision_memories ADD COLUMN IF NOT EXISTS source_decision_record_id UUID",
    "ALTER TABLE decision_memories DROP CONSTRAINT IF EXISTS decision_memories_source_outcome_status_check",
    "ALTER TABLE decision_memories ADD CONSTRAINT decision_memories_source_outcome_status_check CHECK (source_outcome_status IS NULL OR source_outcome_status IN ('CONFIRMED', 'DISCONFIRMED', 'INCONCLUSIVE'))",
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
)

OWNERSHIP_CONSTRAINT_STATEMENTS = (
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
    "CREATE INDEX IF NOT EXISTS idx_action_states_owner ON decision_action_states(owner_id)",
    "CREATE INDEX IF NOT EXISTS idx_latest_verified_actions_owner ON latest_verified_actions(owner_id)",
    "DROP INDEX IF EXISTS uq_memories_owner_category_content",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_memories_owner_category_content ON decision_memories(owner_id, category, normalized_content) WHERE source_action_id IS NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_memories_owner_source_action ON decision_memories(owner_id, source_action_id) WHERE source_action_id IS NOT NULL",
    "CREATE INDEX IF NOT EXISTS idx_memories_owner_updated ON decision_memories(owner_id, updated_at DESC)",
)

PROFILE_SCALAR_FIELDS = (
    "work_location",
    "budget",
    "commute_minutes",
    "preferred_city",
    "family_size",
    "has_pet",
)


def has_profile_value(value: object) -> bool:
    return not (value is None or (isinstance(value, str) and not value.strip()))


def append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def merge_living_profiles(connection: Connection[DictRow]) -> None:
    rows = connection.execute(
        """
        SELECT * FROM living_profiles
        WHERE owner_id IS NOT NULL
        ORDER BY owner_id, updated_at, conversation_id
        """
    ).fetchall()
    rows_by_owner: dict[UUID, list[DictRow]] = {}
    for row in rows:
        rows_by_owner.setdefault(row["owner_id"], []).append(row)

    for owner_id, owner_rows in rows_by_owner.items():
        if len(owner_rows) < 2:
            continue

        scalar_values: dict[str, object] = {
            field: None for field in PROFILE_SCALAR_FIELDS
        }
        insights: list[str] = []
        preference_tags: dict[str, list[str]] = {}
        source_conversation_id = owner_rows[-1]["conversation_id"]
        source_updated_at = owner_rows[-1]["updated_at"]

        for row in owner_rows:
            row_has_update = False
            for field in PROFILE_SCALAR_FIELDS:
                value = row[field]
                if has_profile_value(value):
                    scalar_values[field] = value
                    row_has_update = True

            for insight in row["latest_insights_json"]:
                append_unique(insights, insight)
                row_has_update = True

            for category, values in row["preference_tags_json"].items():
                merged_values = preference_tags.setdefault(category, [])
                for value in values:
                    append_unique(merged_values, value)
                    row_has_update = True

            if row_has_update:
                source_conversation_id = row["conversation_id"]
                source_updated_at = row["updated_at"]

        connection.execute(
            "DELETE FROM living_profiles WHERE owner_id = %s",
            (owner_id,),
        )
        connection.execute(
            """
            INSERT INTO living_profiles(
                owner_id, conversation_id, work_location, budget, commute_minutes,
                preferred_city, family_size, has_pet, latest_insights_json,
                preference_tags_json, updated_at
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            """,
            (
                owner_id,
                source_conversation_id,
                *(scalar_values[field] for field in PROFILE_SCALAR_FIELDS),
                Jsonb(insights),
                Jsonb(preference_tags),
                source_updated_at,
            ),
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
            for statement in OWNERSHIP_BACKFILL_STATEMENTS:
                connection.execute(statement)
            merge_living_profiles(connection)
            for statement in OWNERSHIP_CONSTRAINT_STATEMENTS:
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
