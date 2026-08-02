from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.models.conversation import Conversation, ConversationMessage
from app.models.profile import LivingProfile
from app.models.property import Property
from app.schemas.decision import DecisionReason, DecisionTradeOff
from app.schemas.decision_record import DecisionRecord
from app.stores.database import Database


def now() -> datetime:
    return datetime.now(UTC)


def uuid_value(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(value)


def optional_uuid(value: str | UUID) -> UUID | None:
    try:
        return uuid_value(value)
    except (TypeError, ValueError):
        return None


class ConversationStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def ensure_user(self, user_id: str) -> None:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO anonymous_users(id, created_at)
                VALUES (%s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (uuid_value(user_id), now()),
            )

    def get_or_create(self, conversation_id: str, user_id: str) -> Conversation:
        self.ensure_user(user_id)
        timestamp = now()
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO conversations(id, anonymous_user_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    uuid_value(conversation_id),
                    uuid_value(user_id),
                    timestamp,
                    timestamp,
                ),
            )
        return self.get(conversation_id) or Conversation(conversation_id)

    def get(self, conversation_id: str) -> Conversation | None:
        conversation_uuid = optional_uuid(conversation_id)
        if conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT id FROM conversations WHERE id = %s",
                (conversation_uuid,),
            ).fetchone()
            if row is None:
                return None
            messages = connection.execute(
                """
                SELECT role, content
                FROM conversation_messages
                WHERE conversation_id = %s
                ORDER BY sequence
                """,
                (conversation_uuid,),
            ).fetchall()
        return Conversation(
            conversation_id,
            [
                ConversationMessage(role=row["role"], content=row["content"])
                for row in messages
            ],
        )

    def belongs_to(self, conversation_id: str, user_id: str) -> bool:
        conversation_uuid = optional_uuid(conversation_id)
        user_uuid = optional_uuid(user_id)
        if conversation_uuid is None or user_uuid is None:
            return False
        with self._database.connect() as connection:
            return (
                connection.execute(
                    """
                    SELECT 1
                    FROM conversations
                    WHERE id = %s AND anonymous_user_id = %s
                    """,
                    (conversation_uuid, user_uuid),
                ).fetchone()
                is not None
            )

    def append(self, conversation_id: str, role: str, content: str) -> None:
        conversation_uuid = uuid_value(conversation_id)
        with self._database.connect() as connection:
            connection.execute(
                "SELECT id FROM conversations WHERE id = %s FOR UPDATE",
                (conversation_uuid,),
            )
            row = connection.execute(
                """
                SELECT COALESCE(MAX(sequence), -1) + 1 AS sequence
                FROM conversation_messages
                WHERE conversation_id = %s
                """,
                (conversation_uuid,),
            ).fetchone()
            if row is None:
                raise RuntimeError("Conversation sequence could not be created.")
            connection.execute(
                """
                INSERT INTO conversation_messages(
                    conversation_id, sequence, role, content, created_at
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (conversation_uuid, row["sequence"], role, content, now()),
            )
            connection.execute(
                "UPDATE conversations SET updated_at = %s WHERE id = %s",
                (now(), conversation_uuid),
            )

    def delete(self, conversation_id: str) -> bool:
        conversation_uuid = optional_uuid(conversation_id)
        if conversation_uuid is None:
            return False
        with self._database.connect() as connection:
            return (
                connection.execute(
                    "DELETE FROM conversations WHERE id = %s",
                    (conversation_uuid,),
                ).rowcount
                > 0
            )


class ProfileStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, conversation_id: str) -> LivingProfile | None:
        conversation_uuid = optional_uuid(conversation_id)
        if conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM living_profiles WHERE conversation_id = %s",
                (conversation_uuid,),
            ).fetchone()
        if row is None:
            return None
        return LivingProfile(
            row["work_location"],
            row["budget"],
            row["commute_minutes"],
            row["preferred_city"],
            row["family_size"],
            row["has_pet"],
            list(row["latest_insights_json"]),
            dict(row["preference_tags_json"]),
        )

    def save(self, conversation_id: str, profile: LivingProfile) -> LivingProfile:
        values = (
            uuid_value(conversation_id),
            profile.work_location,
            profile.budget,
            profile.commute_minutes,
            profile.preferred_city,
            profile.family_size,
            profile.has_pet,
            Jsonb(profile.latest_insights),
            Jsonb(profile.preference_tags),
            now(),
        )
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO living_profiles(
                    conversation_id, work_location, budget, commute_minutes,
                    preferred_city, family_size, has_pet, latest_insights_json,
                    preference_tags_json, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (conversation_id) DO UPDATE SET
                    work_location = EXCLUDED.work_location,
                    budget = EXCLUDED.budget,
                    commute_minutes = EXCLUDED.commute_minutes,
                    preferred_city = EXCLUDED.preferred_city,
                    family_size = EXCLUDED.family_size,
                    has_pet = EXCLUDED.has_pet,
                    latest_insights_json = EXCLUDED.latest_insights_json,
                    preference_tags_json = EXCLUDED.preference_tags_json,
                    updated_at = EXCLUDED.updated_at
                """,
                values,
            )
        return self.get(conversation_id) or profile

    def delete(self, conversation_id: str) -> bool:
        conversation_uuid = optional_uuid(conversation_id)
        if conversation_uuid is None:
            return False
        with self._database.connect() as connection:
            return (
                connection.execute(
                    "DELETE FROM living_profiles WHERE conversation_id = %s",
                    (conversation_uuid,),
                ).rowcount
                > 0
            )


class PropertyStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _from(row: dict[str, Any]) -> Property:
        return Property(
            id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            title=row["title"],
            district=row["district"],
            rent=row["rent"],
            area=row["area"],
            bedrooms=row["bedrooms"],
            bathrooms=row["bathrooms"],
            commute_minutes=row["commute_minutes"],
            pet_friendly=row["pet_friendly"],
        )

    def create(self, property_: Property) -> Property:
        if property_.id is None or property_.conversation_id is None:
            raise ValueError("Stored Property requires IDs.")
        timestamp = now()
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO properties(
                    id, conversation_id, title, district, rent, area, bedrooms,
                    bathrooms, commute_minutes, pet_friendly, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid_value(property_.id),
                    uuid_value(property_.conversation_id),
                    property_.title,
                    property_.district,
                    property_.rent,
                    property_.area,
                    property_.bedrooms,
                    property_.bathrooms,
                    property_.commute_minutes,
                    property_.pet_friendly,
                    timestamp,
                    timestamp,
                ),
            )
        return property_

    def list(self, conversation_id: str) -> list[Property]:
        conversation_uuid = optional_uuid(conversation_id)
        if conversation_uuid is None:
            return []
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM properties
                WHERE conversation_id = %s
                ORDER BY created_at
                """,
                (conversation_uuid,),
            ).fetchall()
        return [self._from(row) for row in rows]

    def delete(self, property_id: str, conversation_id: str | None = None) -> bool:
        property_uuid = optional_uuid(property_id)
        conversation_uuid = (
            optional_uuid(conversation_id) if conversation_id is not None else None
        )
        if property_uuid is None or (
            conversation_id is not None and conversation_uuid is None
        ):
            return False
        query, values = (
            ("DELETE FROM properties WHERE id = %s", (property_uuid,))
            if conversation_id is None
            else (
                "DELETE FROM properties WHERE id = %s AND conversation_id = %s",
                (property_uuid, conversation_uuid),
            )
        )
        with self._database.connect() as connection:
            return connection.execute(query, values).rowcount > 0

    def delete_for_owner(self, property_id: str, user_id: str) -> bool:
        property_uuid = optional_uuid(property_id)
        user_uuid = optional_uuid(user_id)
        if property_uuid is None or user_uuid is None:
            return False
        with self._database.connect() as connection:
            return (
                connection.execute(
                    """
                    DELETE FROM properties
                    WHERE id = %s
                      AND conversation_id IN (
                          SELECT id FROM conversations WHERE anonymous_user_id = %s
                      )
                    """,
                    (property_uuid, user_uuid),
                ).rowcount
                > 0
            )

    def delete_conversation(self, conversation_id: str) -> None:
        conversation_uuid = optional_uuid(conversation_id)
        if conversation_uuid is None:
            return
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM properties WHERE conversation_id = %s",
                (conversation_uuid,),
            )


class DecisionRecordStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def save(self, record: DecisionRecord) -> DecisionRecord:
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO decision_records(
                    id, conversation_id, created_at, summary, best_property_id,
                    reasons_json, trade_offs_json, confidence
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid_value(record.id),
                    uuid_value(record.conversation_id),
                    record.created_at,
                    record.summary,
                    uuid_value(record.best_property_id),
                    Jsonb([item.model_dump() for item in record.reasons]),
                    Jsonb([item.model_dump() for item in record.trade_offs]),
                    record.confidence,
                ),
            )
        return record.model_copy(deep=True)

    @staticmethod
    def _from(row: dict[str, Any]) -> DecisionRecord:
        return DecisionRecord(
            id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            created_at=row["created_at"],
            summary=row["summary"],
            best_property_id=str(row["best_property_id"]),
            reasons=[
                DecisionReason.model_validate(item) for item in row["reasons_json"]
            ],
            trade_offs=[
                DecisionTradeOff.model_validate(item) for item in row["trade_offs_json"]
            ],
            confidence=row["confidence"],
        )

    def list_by_conversation(self, conversation_id: str) -> list[DecisionRecord]:
        conversation_uuid = optional_uuid(conversation_id)
        if conversation_uuid is None:
            return []
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM decision_records
                WHERE conversation_id = %s
                ORDER BY created_at DESC
                """,
                (conversation_uuid,),
            ).fetchall()
        return [self._from(row) for row in rows]

    def get_by_id(self, conversation_id: str, record_id: str) -> DecisionRecord | None:
        conversation_uuid = optional_uuid(conversation_id)
        record_uuid = optional_uuid(record_id)
        if conversation_uuid is None or record_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM decision_records
                WHERE conversation_id = %s AND id = %s
                """,
                (conversation_uuid, record_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None

    def delete_conversation(self, conversation_id: str) -> None:
        conversation_uuid = optional_uuid(conversation_id)
        if conversation_uuid is None:
            return
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM decision_records WHERE conversation_id = %s",
                (conversation_uuid,),
            )
