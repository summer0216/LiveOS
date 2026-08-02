import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path: str) -> None:
        self._path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self._path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS anonymous_users (
                  id TEXT PRIMARY KEY, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversations (
                  id TEXT PRIMARY KEY,
                  anonymous_user_id TEXT NOT NULL REFERENCES anonymous_users(id),
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS conversation_messages (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                  sequence INTEGER NOT NULL, role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
                  content TEXT NOT NULL, created_at TEXT NOT NULL,
                  UNIQUE(conversation_id, sequence)
                );
                CREATE TABLE IF NOT EXISTS living_profiles (
                  conversation_id TEXT PRIMARY KEY REFERENCES conversations(id) ON DELETE CASCADE,
                  work_location TEXT, budget INTEGER, commute_minutes INTEGER, preferred_city TEXT,
                  family_size INTEGER, has_pet INTEGER, latest_insights_json TEXT NOT NULL,
                  preference_tags_json TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS properties (
                  id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                  title TEXT, district TEXT, rent INTEGER, area INTEGER, bedrooms INTEGER, bathrooms INTEGER,
                  commute_minutes INTEGER, pet_friendly INTEGER, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS decision_records (
                  id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                  created_at TEXT NOT NULL, summary TEXT NOT NULL, best_property_id TEXT NOT NULL,
                  reasons_json TEXT NOT NULL, trade_offs_json TEXT NOT NULL, confidence REAL
                );
                CREATE TABLE IF NOT EXISTS decision_memories (
                  id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                  category TEXT NOT NULL, content TEXT NOT NULL, normalized_content TEXT NOT NULL,
                  confidence REAL NOT NULL, evidence_record_ids_json TEXT NOT NULL,
                  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                  UNIQUE(conversation_id, category, normalized_content)
                );
                CREATE INDEX IF NOT EXISTS idx_properties_conversation ON properties(conversation_id);
                CREATE INDEX IF NOT EXISTS idx_records_conversation_created ON decision_records(conversation_id, created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_memories_conversation_updated ON decision_memories(conversation_id, updated_at DESC);
                """
            )
