from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.models.action_progress import (
    ActionProgressStatus,
    DecisionActionState,
    LatestVerifiedAction,
    VerificationEvidence,
    VerificationOutcomeStatus,
)
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


def resolve_owner_id(database: Database, conversation_id: str | UUID) -> UUID | None:
    conversation_uuid = optional_uuid(conversation_id)
    if conversation_uuid is None:
        return None
    with database.connect() as connection:
        row = connection.execute(
            "SELECT anonymous_user_id FROM conversations WHERE id = %s",
            (conversation_uuid,),
        ).fetchone()
    return row["anonymous_user_id"] if row is not None else None


def validate_owner_source(
    database: Database,
    owner_id: str | UUID,
    conversation_id: str | UUID | None,
) -> None:
    if conversation_id is None:
        return
    if resolve_owner_id(database, conversation_id) != uuid_value(owner_id):
        raise ValueError("Source conversation does not belong to Owner.")


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

    def owner_id(self, conversation_id: str) -> str | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        return str(owner_id) if owner_id is not None else None

    def list_ids_by_owner_activity(self, user_id: str) -> list[str]:
        user_uuid = optional_uuid(user_id)
        if user_uuid is None:
            return []
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id
                FROM conversations
                WHERE anonymous_user_id = %s
                ORDER BY updated_at DESC, created_at DESC, id DESC
                """,
                (user_uuid,),
            ).fetchall()
        return [str(row["id"]) for row in rows]

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
        owner_id = resolve_owner_id(self._database, conversation_id)
        if owner_id is None:
            return None
        return self.get_by_owner(owner_id)

    def get_by_owner(self, owner_id: str | UUID) -> LivingProfile | None:
        owner_uuid = optional_uuid(owner_id)
        if owner_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM living_profiles WHERE owner_id = %s",
                (owner_uuid,),
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
        owner_id = resolve_owner_id(self._database, conversation_id)
        if owner_id is None:
            raise ValueError("Conversation owner could not be resolved.")
        return self.save_for_owner(owner_id, profile, conversation_id)

    def save_for_owner(
        self,
        owner_id: str | UUID,
        profile: LivingProfile,
        conversation_id: str | UUID | None = None,
    ) -> LivingProfile:
        owner_uuid = uuid_value(owner_id)
        validate_owner_source(self._database, owner_uuid, conversation_id)
        values = (
            optional_uuid(conversation_id),
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
                    owner_id, conversation_id, work_location, budget, commute_minutes,
                    preferred_city, family_size, has_pet, latest_insights_json,
                    preference_tags_json, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id) DO UPDATE SET
                    conversation_id = EXCLUDED.conversation_id,
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
                (owner_uuid, *values),
            )
        return self.get_by_owner(owner_uuid) or profile

    def delete(self, conversation_id: str) -> bool:
        conversation_uuid = optional_uuid(conversation_id)
        if conversation_uuid is None:
            return False
        with self._database.connect() as connection:
            return (
                connection.execute(
                    """
                    DELETE FROM living_profiles
                    WHERE owner_id = (
                        SELECT anonymous_user_id FROM conversations WHERE id = %s
                    )
                    """,
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
            conversation_id=(
                str(row["conversation_id"])
                if row["conversation_id"] is not None
                else None
            ),
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
        owner_id = resolve_owner_id(self._database, property_.conversation_id)
        if owner_id is None:
            raise ValueError("Conversation owner could not be resolved.")
        return self.create_for_owner(owner_id, property_)

    def create_for_owner(self, owner_id: str | UUID, property_: Property) -> Property:
        if property_.id is None:
            raise ValueError("Stored Property requires an ID.")
        validate_owner_source(self._database, owner_id, property_.conversation_id)
        timestamp = now()
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO properties(
                    id, owner_id, conversation_id, title, district, rent, area, bedrooms,
                    bathrooms, commute_minutes, pet_friendly, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid_value(property_.id),
                    uuid_value(owner_id),
                    optional_uuid(property_.conversation_id),
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
        owner_id = resolve_owner_id(self._database, conversation_id)
        if owner_id is None:
            return []
        return self.list_by_owner(owner_id)

    def list_by_owner(self, owner_id: str | UUID) -> list[Property]:
        owner_uuid = optional_uuid(owner_id)
        if owner_uuid is None:
            return []
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM properties
                WHERE owner_id = %s
                ORDER BY created_at
                """,
                (owner_uuid,),
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
                """
                DELETE FROM properties WHERE id = %s AND owner_id = (
                    SELECT anonymous_user_id FROM conversations WHERE id = %s
                )
                """,
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
                      AND owner_id = %s
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
        owner_id = resolve_owner_id(self._database, record.conversation_id)
        if owner_id is None:
            raise ValueError("Conversation owner could not be resolved.")
        return self.save_for_owner(owner_id, record)

    def save_for_owner(
        self, owner_id: str | UUID, record: DecisionRecord
    ) -> DecisionRecord:
        validate_owner_source(self._database, owner_id, record.conversation_id)
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO decision_records(
                    id, owner_id, conversation_id, created_at, summary, best_property_id,
                    reasons_json, trade_offs_json, confidence, decision_gap
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid_value(record.id),
                    uuid_value(owner_id),
                    uuid_value(record.conversation_id),
                    record.created_at,
                    record.summary,
                    uuid_value(record.best_property_id),
                    Jsonb([item.model_dump() for item in record.reasons]),
                    Jsonb([item.model_dump() for item in record.trade_offs]),
                    record.confidence,
                    record.decision_gap,
                ),
            )
        return record.model_copy(deep=True)

    @staticmethod
    def _from(row: dict[str, Any]) -> DecisionRecord:
        return DecisionRecord(
            id=str(row["id"]),
            conversation_id=(
                str(row["conversation_id"])
                if row["conversation_id"] is not None
                else str(row["owner_id"])
            ),
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
            decision_gap=row.get("decision_gap"),
        )

    def list_by_conversation(self, conversation_id: str) -> list[DecisionRecord]:
        owner_id = resolve_owner_id(self._database, conversation_id)
        if owner_id is None:
            return []
        return self.list_by_owner(owner_id)

    def list_by_owner(self, owner_id: str | UUID) -> list[DecisionRecord]:
        owner_uuid = optional_uuid(owner_id)
        if owner_uuid is None:
            return []
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM decision_records
                WHERE owner_id = %s
                ORDER BY created_at DESC
                """,
                (owner_uuid,),
            ).fetchall()
        return [self._from(row) for row in rows]

    def get_by_id(self, conversation_id: str, record_id: str) -> DecisionRecord | None:
        owner_uuid = resolve_owner_id(self._database, conversation_id)
        record_uuid = optional_uuid(record_id)
        if owner_uuid is None or record_uuid is None:
            return None
        return self.get_by_id_for_owner(owner_uuid, record_uuid)

    def get_by_id_for_owner(
        self, owner_id: str | UUID, record_id: str | UUID
    ) -> DecisionRecord | None:
        owner_uuid = optional_uuid(owner_id)
        record_uuid = optional_uuid(record_id)
        if owner_uuid is None or record_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM decision_records
                WHERE owner_id = %s AND id = %s
                """,
                (owner_uuid, record_uuid),
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


class DecisionActionStateStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def save(self, state: DecisionActionState) -> DecisionActionState:
        owner_id = resolve_owner_id(self._database, state.conversation_id)
        if owner_id is None:
            raise ValueError("Conversation owner could not be resolved.")
        validate_owner_source(self._database, owner_id, state.conversation_id)
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO decision_action_states(
                    id, owner_id, conversation_id, decision_record_id,
                    action_key, next_text, status, outcome_status,
                    verification_evidence_json, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id, conversation_id) DO UPDATE SET
                    id = EXCLUDED.id,
                    decision_record_id = EXCLUDED.decision_record_id,
                    action_key = EXCLUDED.action_key,
                    next_text = EXCLUDED.next_text,
                    status = EXCLUDED.status,
                    outcome_status = EXCLUDED.outcome_status,
                    verification_evidence_json = EXCLUDED.verification_evidence_json,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    uuid_value(state.id),
                    owner_id,
                    uuid_value(state.conversation_id),
                    uuid_value(state.decision_record_id),
                    state.action_key,
                    state.next_text,
                    state.status.value if state.status is not None else None,
                    (
                        state.outcome_status.value
                        if state.outcome_status is not None
                        else None
                    ),
                    Jsonb(
                        [
                            item.model_dump(mode="json")
                            for item in state.verification_evidence
                        ]
                    ),
                    state.created_at,
                    state.updated_at,
                ),
            )
        return state.model_copy(deep=True)

    def get(self, conversation_id: str) -> DecisionActionState | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM decision_action_states
                WHERE owner_id = %s AND conversation_id = %s
                """,
                (owner_id, conversation_uuid),
            ).fetchone()
        if row is None:
            return None
        return DecisionActionState(
            id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            decision_record_id=str(row["decision_record_id"]),
            action_key=row["action_key"],
            next_text=row["next_text"],
            status=(
                ActionProgressStatus(row["status"])
                if row["status"] is not None
                else None
            ),
            outcome_status=(
                VerificationOutcomeStatus(row["outcome_status"])
                if row["outcome_status"] is not None
                else None
            ),
            verification_evidence=tuple(
                VerificationEvidence.model_validate(item)
                for item in row["verification_evidence_json"]
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def delete_conversation(self, conversation_id: str) -> None:
        conversation_uuid = optional_uuid(conversation_id)
        if conversation_uuid is None:
            return
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM decision_action_states WHERE conversation_id = %s",
                (conversation_uuid,),
            )


class LatestVerifiedActionStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def save(self, action: LatestVerifiedAction) -> LatestVerifiedAction:
        owner_id = resolve_owner_id(self._database, action.conversation_id)
        if owner_id is None:
            raise ValueError("Conversation owner could not be resolved.")
        validate_owner_source(self._database, owner_id, action.conversation_id)
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO latest_verified_actions(
                    owner_id, conversation_id, action_id, decision_record_id,
                    action_key, next_text, status, outcome_status,
                    verification_evidence_json, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id, conversation_id) DO UPDATE SET
                    action_id = EXCLUDED.action_id,
                    decision_record_id = EXCLUDED.decision_record_id,
                    action_key = EXCLUDED.action_key,
                    next_text = EXCLUDED.next_text,
                    status = EXCLUDED.status,
                    outcome_status = EXCLUDED.outcome_status,
                    verification_evidence_json = EXCLUDED.verification_evidence_json,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at
                """,
                (
                    owner_id,
                    uuid_value(action.conversation_id),
                    uuid_value(action.action_id),
                    uuid_value(action.decision_record_id),
                    action.action_key,
                    action.next_text,
                    action.status.value,
                    action.outcome_status.value,
                    Jsonb(
                        [
                            item.model_dump(mode="json")
                            for item in action.verification_evidence
                        ]
                    ),
                    action.created_at,
                    action.updated_at,
                ),
            )
        return action.model_copy(deep=True)

    def get(self, conversation_id: str) -> LatestVerifiedAction | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM latest_verified_actions
                WHERE owner_id = %s AND conversation_id = %s
                """,
                (owner_id, conversation_uuid),
            ).fetchone()
        if row is None:
            return None
        return LatestVerifiedAction(
            action_id=str(row["action_id"]),
            conversation_id=str(row["conversation_id"]),
            decision_record_id=str(row["decision_record_id"]),
            action_key=row["action_key"],
            next_text=row["next_text"],
            status=ActionProgressStatus(row["status"]),
            outcome_status=VerificationOutcomeStatus(row["outcome_status"]),
            verification_evidence=tuple(
                VerificationEvidence.model_validate(item)
                for item in row["verification_evidence_json"]
            ),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def delete_conversation(self, conversation_id: str) -> None:
        conversation_uuid = optional_uuid(conversation_id)
        if conversation_uuid is None:
            return
        with self._database.connect() as connection:
            connection.execute(
                "DELETE FROM latest_verified_actions WHERE conversation_id = %s",
                (conversation_uuid,),
            )
