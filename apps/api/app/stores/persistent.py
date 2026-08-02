import json
from datetime import UTC, datetime

from app.models.conversation import Conversation, ConversationMessage
from app.models.profile import LivingProfile
from app.models.property import Property
from app.schemas.decision_record import DecisionRecord
from app.stores.database import Database


def now() -> str:
    return datetime.now(UTC).isoformat()


class ConversationStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def ensure_user(self, user_id: str) -> None:
        with self._database.connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO anonymous_users(id, created_at) VALUES (?, ?)",
                (user_id, now()),
            )

    def get_or_create(self, conversation_id: str, user_id: str) -> Conversation:
        self.ensure_user(user_id)
        timestamp = now()
        with self._database.connect() as c:
            c.execute(
                "INSERT OR IGNORE INTO conversations(id, anonymous_user_id, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (conversation_id, user_id, timestamp, timestamp),
            )
        return self.get(conversation_id) or Conversation(conversation_id)

    def get(self, conversation_id: str) -> Conversation | None:
        with self._database.connect() as c:
            row = c.execute(
                "SELECT id FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if row is None:
                return None
            messages = c.execute(
                "SELECT role, content FROM conversation_messages WHERE conversation_id = ? ORDER BY sequence",
                (conversation_id,),
            ).fetchall()
        return Conversation(
            conversation_id,
            [
                ConversationMessage(role=row["role"], content=row["content"])
                for row in messages
            ],
        )

    def belongs_to(self, conversation_id: str, user_id: str) -> bool:
        with self._database.connect() as c:
            return (
                c.execute(
                    "SELECT 1 FROM conversations WHERE id = ? AND anonymous_user_id = ?",
                    (conversation_id, user_id),
                ).fetchone()
                is not None
            )

    def append(self, conversation_id: str, role: str, content: str) -> None:
        with self._database.connect() as c:
            sequence = c.execute(
                "SELECT COALESCE(MAX(sequence), -1) + 1 FROM conversation_messages WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()[0]
            c.execute(
                "INSERT INTO conversation_messages(conversation_id, sequence, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
                (conversation_id, sequence, role, content, now()),
            )
            c.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (now(), conversation_id),
            )

    def delete(self, conversation_id: str) -> bool:
        with self._database.connect() as c:
            return (
                c.execute(
                    "DELETE FROM conversations WHERE id = ?", (conversation_id,)
                ).rowcount
                > 0
            )


class ProfileStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, conversation_id: str) -> LivingProfile | None:
        with self._database.connect() as c:
            row = c.execute(
                "SELECT * FROM living_profiles WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
        if row is None:
            return None
        return LivingProfile(
            row["work_location"],
            row["budget"],
            row["commute_minutes"],
            row["preferred_city"],
            row["family_size"],
            None if row["has_pet"] is None else bool(row["has_pet"]),
            json.loads(row["latest_insights_json"]),
            json.loads(row["preference_tags_json"]),
        )

    def save(self, conversation_id: str, profile: LivingProfile) -> LivingProfile:
        values = (
            conversation_id,
            profile.work_location,
            profile.budget,
            profile.commute_minutes,
            profile.preferred_city,
            profile.family_size,
            None if profile.has_pet is None else int(profile.has_pet),
            json.dumps(profile.latest_insights),
            json.dumps(profile.preference_tags),
            now(),
        )
        with self._database.connect() as c:
            c.execute(
                "INSERT INTO living_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(conversation_id) DO UPDATE SET work_location=excluded.work_location,budget=excluded.budget,commute_minutes=excluded.commute_minutes,preferred_city=excluded.preferred_city,family_size=excluded.family_size,has_pet=excluded.has_pet,latest_insights_json=excluded.latest_insights_json,preference_tags_json=excluded.preference_tags_json,updated_at=excluded.updated_at",
                values,
            )
        return self.get(conversation_id) or profile

    def delete(self, conversation_id: str) -> bool:
        with self._database.connect() as c:
            return (
                c.execute(
                    "DELETE FROM living_profiles WHERE conversation_id = ?",
                    (conversation_id,),
                ).rowcount
                > 0
            )


class PropertyStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _from(row: object) -> Property:
        return Property(
            id=row["id"],
            conversation_id=row["conversation_id"],
            title=row["title"],
            district=row["district"],
            rent=row["rent"],
            area=row["area"],
            bedrooms=row["bedrooms"],
            bathrooms=row["bathrooms"],
            commute_minutes=row["commute_minutes"],
            pet_friendly=None
            if row["pet_friendly"] is None
            else bool(row["pet_friendly"]),
        )

    def create(self, property_: Property) -> Property:
        timestamp = now()
        with self._database.connect() as c:
            c.execute(
                "INSERT INTO properties VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    property_.id,
                    property_.conversation_id,
                    property_.title,
                    property_.district,
                    property_.rent,
                    property_.area,
                    property_.bedrooms,
                    property_.bathrooms,
                    property_.commute_minutes,
                    None
                    if property_.pet_friendly is None
                    else int(property_.pet_friendly),
                    timestamp,
                    timestamp,
                ),
            )
        return property_

    def list(self, conversation_id: str) -> list[Property]:
        with self._database.connect() as c:
            rows = c.execute(
                "SELECT * FROM properties WHERE conversation_id = ? ORDER BY created_at",
                (conversation_id,),
            ).fetchall()
        return [self._from(row) for row in rows]

    def delete(self, property_id: str, conversation_id: str | None = None) -> bool:
        query, values = (
            ("DELETE FROM properties WHERE id = ?", (property_id,))
            if conversation_id is None
            else (
                "DELETE FROM properties WHERE id = ? AND conversation_id = ?",
                (property_id, conversation_id),
            )
        )
        with self._database.connect() as c:
            return c.execute(query, values).rowcount > 0

    def delete_for_owner(self, property_id: str, user_id: str) -> bool:
        with self._database.connect() as c:
            return (
                c.execute(
                    "DELETE FROM properties WHERE id = ? AND conversation_id IN (SELECT id FROM conversations WHERE anonymous_user_id = ?)",
                    (property_id, user_id),
                ).rowcount
                > 0
            )

    def delete_conversation(self, conversation_id: str) -> None:
        with self._database.connect() as c:
            c.execute(
                "DELETE FROM properties WHERE conversation_id = ?", (conversation_id,)
            )


class DecisionRecordStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def save(self, record: DecisionRecord) -> DecisionRecord:
        with self._database.connect() as c:
            c.execute(
                "INSERT INTO decision_records VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record.id,
                    record.conversation_id,
                    record.created_at.isoformat(),
                    record.summary,
                    record.best_property_id,
                    json.dumps([item.model_dump() for item in record.reasons]),
                    json.dumps([item.model_dump() for item in record.trade_offs]),
                    record.confidence,
                ),
            )
        return record.model_copy(deep=True)

    def _from(self, row: object) -> DecisionRecord:
        from app.schemas.decision import DecisionReason, DecisionTradeOff

        return DecisionRecord(
            id=row["id"],
            conversation_id=row["conversation_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            summary=row["summary"],
            best_property_id=row["best_property_id"],
            reasons=[
                DecisionReason.model_validate(item)
                for item in json.loads(row["reasons_json"])
            ],
            trade_offs=[
                DecisionTradeOff.model_validate(item)
                for item in json.loads(row["trade_offs_json"])
            ],
            confidence=row["confidence"],
        )

    def list_by_conversation(self, conversation_id: str) -> list[DecisionRecord]:
        with self._database.connect() as c:
            rows = c.execute(
                "SELECT * FROM decision_records WHERE conversation_id = ? ORDER BY created_at DESC",
                (conversation_id,),
            ).fetchall()
        return [self._from(row) for row in rows]

    def get_by_id(self, conversation_id: str, record_id: str) -> DecisionRecord | None:
        with self._database.connect() as c:
            row = c.execute(
                "SELECT * FROM decision_records WHERE conversation_id = ? AND id = ?",
                (conversation_id, record_id),
            ).fetchone()
        return self._from(row) if row is not None else None

    def delete_conversation(self, conversation_id: str) -> None:
        with self._database.connect() as c:
            c.execute(
                "DELETE FROM decision_records WHERE conversation_id = ?",
                (conversation_id,),
            )
