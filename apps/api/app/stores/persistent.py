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
from app.models.decision_geography import DecisionGeography
from app.models.decision_unknown import DecisionUnknown, DecisionUnknownStatus
from app.models.living_time import LivingTimeRelationship
from app.models.possible_life import PossibleLife
from app.models.possible_life_meaningful_unknown import PossibleLifeMeaningfulUnknown
from app.models.possible_life_personal_meaning import PossibleLifePersonalMeaning
from app.models.possible_life_reality_action import (
    PossibleLifeRealityAction,
    PossibleLifeRealityActionType,
)
from app.models.profile import LivingProfile
from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
    PropertyRentSource,
)
from app.models.reality_need import RealityNeed, RealityNeedResolutionMode
from app.models.work_subject import WorkSubject
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
            layout_requirement=row.get("layout_requirement"),
            geographic_identity=row.get("geographic_identity"),
            geographic_precision=(
                GeographicPrecision(row["geographic_precision"])
                if row.get("geographic_precision") is not None
                else None
            ),
            geographic_status=GeographicStatus(
                row.get("geographic_status", GeographicStatus.UNRESOLVED.value)
            ),
            lng=row.get("lng"),
            lat=row.get("lat"),
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
            profile.geographic_identity,
            profile.geographic_precision.value
            if profile.geographic_precision is not None
            else None,
            profile.geographic_status.value,
            profile.lng,
            profile.lat,
            profile.layout_requirement,
            now(),
        )
        with self._database.connect() as connection:
            connection.execute(
                """
                INSERT INTO living_profiles(
                    owner_id, conversation_id, work_location, budget, commute_minutes,
                    preferred_city, family_size, has_pet, latest_insights_json,
                    preference_tags_json, geographic_identity, geographic_precision,
                    geographic_status, lng, lat, layout_requirement, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    geographic_identity = EXCLUDED.geographic_identity,
                    geographic_precision = EXCLUDED.geographic_precision,
                    geographic_status = EXCLUDED.geographic_status,
                    lng = EXCLUDED.lng,
                    lat = EXCLUDED.lat,
                    layout_requirement = EXCLUDED.layout_requirement,
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


class WorkSubjectStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _from(row: dict[str, Any]) -> WorkSubject:
        return WorkSubject(
            identity=row["identity"],
            geographic_identity=row["geographic_identity"],
            geographic_precision="PLACE",
            geographic_status="GROUNDED",
            lng=row["lng"],
            lat=row["lat"],
            relationship="WORK",
        )

    def get(self, conversation_id: str) -> WorkSubject | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        if owner_id is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM work_subjects WHERE owner_id = %s",
                (owner_id,),
            ).fetchone()
        return self._from(row) if row is not None else None

    def save(self, conversation_id: str, subject: WorkSubject) -> WorkSubject:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or conversation_uuid is None:
            raise ValueError("Conversation owner could not be resolved.")
        with self._database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO work_subjects(
                    owner_id, source_conversation_id, relationship, identity,
                    geographic_identity, geographic_precision, geographic_status,
                    lng, lat, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id) DO UPDATE SET
                    source_conversation_id = EXCLUDED.source_conversation_id,
                    relationship = EXCLUDED.relationship,
                    identity = EXCLUDED.identity,
                    geographic_identity = EXCLUDED.geographic_identity,
                    geographic_precision = EXCLUDED.geographic_precision,
                    geographic_status = EXCLUDED.geographic_status,
                    lng = EXCLUDED.lng,
                    lat = EXCLUDED.lat,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                (
                    owner_id,
                    conversation_uuid,
                    subject.relationship,
                    subject.identity,
                    subject.geographic_identity,
                    subject.geographic_precision,
                    subject.geographic_status,
                    subject.lng,
                    subject.lat,
                    now(),
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("Work Subject could not be persisted.")
        return self._from(row)


class LivingTimeRelationshipStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _from(row: dict[str, Any]) -> LivingTimeRelationship:
        return LivingTimeRelationship(
            residence_property_id=str(row["residence_property_id"]),
            residence_identity=row["residence_identity"],
            residence_geographic_identity=row["residence_geographic_identity"],
            work_subject_identity=row["work_subject_identity"],
            work_geographic_identity=row["work_geographic_identity"],
            travel_minutes=row["travel_minutes"],
            travel_mode=CommuteMode(row["travel_mode"]),
            evidence_source=row["evidence_source"],
            evidence_reference=row["evidence_reference"],
        )

    def get(
        self, conversation_id: str, residence_property_id: str,
    ) -> LivingTimeRelationship | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(residence_property_id)
        if owner_id is None or property_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM living_time_relationships
                WHERE owner_id = %s AND residence_property_id = %s
                """,
                (owner_id, property_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None

    def save(
        self, conversation_id: str, relationship: LivingTimeRelationship,
    ) -> LivingTimeRelationship:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        property_uuid = optional_uuid(relationship.residence_property_id)
        if owner_id is None or conversation_uuid is None or property_uuid is None:
            raise ValueError("Living Time endpoints could not be resolved.")
        with self._database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO living_time_relationships(
                    owner_id, source_conversation_id, residence_property_id,
                    residence_identity, residence_geographic_identity,
                    work_subject_identity, work_geographic_identity,
                    travel_minutes, travel_mode, evidence_source,
                    evidence_reference, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id, residence_property_id) DO UPDATE SET
                    source_conversation_id = EXCLUDED.source_conversation_id,
                    residence_identity = EXCLUDED.residence_identity,
                    residence_geographic_identity = EXCLUDED.residence_geographic_identity,
                    work_subject_identity = EXCLUDED.work_subject_identity,
                    work_geographic_identity = EXCLUDED.work_geographic_identity,
                    travel_minutes = EXCLUDED.travel_minutes,
                    travel_mode = EXCLUDED.travel_mode,
                    evidence_source = EXCLUDED.evidence_source,
                    evidence_reference = EXCLUDED.evidence_reference,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                (
                    owner_id, conversation_uuid, property_uuid,
                    relationship.residence_identity,
                    relationship.residence_geographic_identity,
                    relationship.work_subject_identity,
                    relationship.work_geographic_identity,
                    relationship.travel_minutes,
                    relationship.travel_mode.value,
                    relationship.evidence_source,
                    relationship.evidence_reference,
                    now(),
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("Living Time relationship could not be persisted.")
        return self._from(row)


class PossibleLifeStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def owner_id(self, conversation_id: str) -> str | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        return str(owner_id) if owner_id is not None else None

    @staticmethod
    def _from(row: dict[str, Any]) -> PossibleLife:
        return PossibleLife(
            id=str(row["id"]),
            work_subject_owner_id=str(row["owner_id"]),
            residence_property_id=str(row["residence_property_id"]),
            living_time_residence_property_id=str(
                row["living_time_residence_property_id"]
            ),
            personal_meaning_reference=row["personal_meaning_reference"],
        )

    def save(self, conversation_id: str, possible_life: PossibleLife) -> PossibleLife:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        residence_uuid = optional_uuid(possible_life.residence_property_id)
        living_time_uuid = optional_uuid(
            possible_life.living_time_residence_property_id
        )
        if (
            owner_id is None
            or conversation_uuid is None
            or residence_uuid is None
            or living_time_uuid is None
            or str(owner_id) != possible_life.work_subject_owner_id
        ):
            raise ValueError("Possible Life references could not be resolved.")
        timestamp = now()
        with self._database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO possible_lives(
                    id, owner_id, source_conversation_id, residence_property_id,
                    living_time_residence_property_id,
                    personal_meaning_reference, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id, residence_property_id) DO UPDATE SET
                    source_conversation_id = EXCLUDED.source_conversation_id,
                    living_time_residence_property_id =
                        EXCLUDED.living_time_residence_property_id,
                    personal_meaning_reference = EXCLUDED.personal_meaning_reference,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                (
                    uuid_value(possible_life.id),
                    owner_id,
                    conversation_uuid,
                    residence_uuid,
                    living_time_uuid,
                    possible_life.personal_meaning_reference,
                    timestamp,
                    timestamp,
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("Possible Life could not be persisted.")
        return self._from(row)

    def list(self, conversation_id: str) -> list[PossibleLife]:
        owner_id = resolve_owner_id(self._database, conversation_id)
        if owner_id is None:
            return []
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM possible_lives
                WHERE owner_id = %s
                ORDER BY created_at, id
                """,
                (owner_id,),
            ).fetchall()
        return [self._from(row) for row in rows]

    def get(
        self, conversation_id: str, possible_life_id: str,
    ) -> PossibleLife | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        possible_life_uuid = optional_uuid(possible_life_id)
        if owner_id is None or possible_life_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM possible_lives
                WHERE owner_id = %s AND id = %s
                """,
                (owner_id, possible_life_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None


class PossibleLifePersonalMeaningStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _from(row: dict[str, Any]) -> PossibleLifePersonalMeaning:
        return PossibleLifePersonalMeaning(
            id=str(row["id"]),
            possible_life_id=str(row["possible_life_id"]),
            meaning=row["meaning"],
            living_time_residence_property_id=str(
                row["living_time_residence_property_id"]
            ),
            actual_travel_minutes=row["actual_travel_minutes"],
            actual_travel_mode=CommuteMode(row["actual_travel_mode"]),
            route_evidence_source=row["route_evidence_source"],
            route_evidence_reference=row["route_evidence_reference"],
            requirement_reference=row["requirement_reference"],
            maximum_commute_minutes=row["maximum_commute_minutes"],
            requirement_satisfied=row["requirement_satisfied"],
        )

    def save(
        self,
        conversation_id: str,
        personal_meaning: PossibleLifePersonalMeaning,
    ) -> PossibleLifePersonalMeaning:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        possible_life_uuid = optional_uuid(personal_meaning.possible_life_id)
        relationship_uuid = optional_uuid(
            personal_meaning.living_time_residence_property_id
        )
        if (
            owner_id is None
            or conversation_uuid is None
            or possible_life_uuid is None
            or relationship_uuid is None
        ):
            raise ValueError("Possible Life Personal Meaning references are invalid.")
        timestamp = now()
        with self._database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO possible_life_personal_meanings(
                    id, owner_id, source_conversation_id, possible_life_id,
                    living_time_residence_property_id, meaning,
                    actual_travel_minutes, actual_travel_mode,
                    route_evidence_source, route_evidence_reference,
                    requirement_reference, maximum_commute_minutes,
                    requirement_satisfied, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (owner_id, possible_life_id) DO UPDATE SET
                    source_conversation_id = EXCLUDED.source_conversation_id,
                    living_time_residence_property_id =
                        EXCLUDED.living_time_residence_property_id,
                    meaning = EXCLUDED.meaning,
                    actual_travel_minutes = EXCLUDED.actual_travel_minutes,
                    actual_travel_mode = EXCLUDED.actual_travel_mode,
                    route_evidence_source = EXCLUDED.route_evidence_source,
                    route_evidence_reference = EXCLUDED.route_evidence_reference,
                    requirement_reference = EXCLUDED.requirement_reference,
                    maximum_commute_minutes = EXCLUDED.maximum_commute_minutes,
                    requirement_satisfied = EXCLUDED.requirement_satisfied,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                (
                    uuid_value(personal_meaning.id),
                    owner_id,
                    conversation_uuid,
                    possible_life_uuid,
                    relationship_uuid,
                    personal_meaning.meaning,
                    personal_meaning.actual_travel_minutes,
                    personal_meaning.actual_travel_mode.value,
                    personal_meaning.route_evidence_source,
                    personal_meaning.route_evidence_reference,
                    personal_meaning.requirement_reference,
                    personal_meaning.maximum_commute_minutes,
                    personal_meaning.requirement_satisfied,
                    timestamp,
                    timestamp,
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("Possible Life Personal Meaning could not be persisted.")
        return self._from(row)

    def get(
        self, conversation_id: str, possible_life_id: str,
    ) -> PossibleLifePersonalMeaning | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        possible_life_uuid = optional_uuid(possible_life_id)
        if owner_id is None or possible_life_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM possible_life_personal_meanings
                WHERE owner_id = %s AND possible_life_id = %s
                """,
                (owner_id, possible_life_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None

    def list(self, conversation_id: str) -> list[PossibleLifePersonalMeaning]:
        owner_id = resolve_owner_id(self._database, conversation_id)
        if owner_id is None:
            return []
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM possible_life_personal_meanings
                WHERE owner_id = %s
                ORDER BY created_at, id
                """,
                (owner_id,),
            ).fetchall()
        return [self._from(row) for row in rows]


class PossibleLifeMeaningfulUnknownStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _from(row: dict[str, Any]) -> PossibleLifeMeaningfulUnknown:
        return PossibleLifeMeaningfulUnknown(
            id=str(row["id"]),
            possible_life_id=str(row["possible_life_id"]),
            personal_meaning_id=str(row["personal_meaning_id"]),
            question=row["question"],
            why_it_matters=row["why_it_matters"],
            state_hash=row["state_hash"],
        )

    def save(
        self,
        conversation_id: str,
        unknown: PossibleLifeMeaningfulUnknown,
    ) -> PossibleLifeMeaningfulUnknown:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        possible_life_uuid = optional_uuid(unknown.possible_life_id)
        personal_meaning_uuid = optional_uuid(unknown.personal_meaning_id)
        if (
            owner_id is None
            or conversation_uuid is None
            or possible_life_uuid is None
            or personal_meaning_uuid is None
        ):
            raise ValueError("Possible Life Meaningful Unknown references are invalid.")
        timestamp = now()
        with self._database.connect() as connection:
            references = connection.execute(
                """
                SELECT 1
                FROM possible_lives AS possible_life
                JOIN possible_life_personal_meanings AS personal_meaning
                  ON personal_meaning.owner_id = possible_life.owner_id
                 AND personal_meaning.possible_life_id = possible_life.id
                WHERE possible_life.owner_id = %s
                  AND possible_life.id = %s
                  AND personal_meaning.id = %s
                """,
                (owner_id, possible_life_uuid, personal_meaning_uuid),
            ).fetchone()
            if references is None:
                raise ValueError(
                    "Possible Life Meaningful Unknown references are inconsistent."
                )
            row = connection.execute(
                """
                INSERT INTO possible_life_meaningful_unknowns(
                    id, owner_id, source_conversation_id, possible_life_id,
                    personal_meaning_id, question, why_it_matters, state_hash,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id, possible_life_id) DO UPDATE SET
                    source_conversation_id = EXCLUDED.source_conversation_id,
                    personal_meaning_id = EXCLUDED.personal_meaning_id,
                    question = EXCLUDED.question,
                    why_it_matters = EXCLUDED.why_it_matters,
                    state_hash = EXCLUDED.state_hash,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                (
                    uuid_value(unknown.id),
                    owner_id,
                    conversation_uuid,
                    possible_life_uuid,
                    personal_meaning_uuid,
                    unknown.question,
                    unknown.why_it_matters,
                    unknown.state_hash,
                    timestamp,
                    timestamp,
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("Possible Life Meaningful Unknown could not be persisted.")
        return self._from(row)

    def get(
        self, conversation_id: str, possible_life_id: str,
    ) -> PossibleLifeMeaningfulUnknown | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        possible_life_uuid = optional_uuid(possible_life_id)
        if owner_id is None or possible_life_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM possible_life_meaningful_unknowns
                WHERE owner_id = %s AND possible_life_id = %s
                """,
                (owner_id, possible_life_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None


class RealityNeedStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _from(row: dict[str, Any]) -> RealityNeed:
        return RealityNeed(
            id=str(row["id"]),
            possible_life_id=str(row["possible_life_id"]),
            meaningful_unknown_id=str(row["meaningful_unknown_id"]),
            needed_reality=row["needed_reality"],
            resolution_mode=RealityNeedResolutionMode(row["resolution_mode"]),
            known_reality_reference=row["known_reality_reference"],
            state_hash=row["state_hash"],
        )

    def save(self, conversation_id: str, need: RealityNeed) -> RealityNeed:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        possible_life_uuid = optional_uuid(need.possible_life_id)
        unknown_uuid = optional_uuid(need.meaningful_unknown_id)
        if (
            owner_id is None
            or conversation_uuid is None
            or possible_life_uuid is None
            or unknown_uuid is None
            or not need.needed_reality.strip()
            or (
                need.resolution_mode == RealityNeedResolutionMode.ALREADY_KNOWN
            ) != (need.known_reality_reference is not None)
        ):
            raise ValueError("Reality Need references or resolution mode are invalid.")
        timestamp = now()
        with self._database.connect() as connection:
            references = connection.execute(
                """
                SELECT 1
                FROM possible_life_meaningful_unknowns AS unknown
                JOIN possible_lives AS possible_life
                  ON possible_life.id = unknown.possible_life_id
                 AND possible_life.owner_id = unknown.owner_id
                WHERE unknown.owner_id = %s
                  AND unknown.id = %s
                  AND possible_life.id = %s
                """,
                (owner_id, unknown_uuid, possible_life_uuid),
            ).fetchone()
            if references is None:
                raise ValueError("Reality Need must reference the same Possible Life.")
            row = connection.execute(
                """
                INSERT INTO reality_needs(
                    id, owner_id, source_conversation_id, possible_life_id,
                    meaningful_unknown_id, needed_reality, resolution_mode,
                    known_reality_reference, state_hash, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id, meaningful_unknown_id) DO UPDATE SET
                    source_conversation_id = EXCLUDED.source_conversation_id,
                    needed_reality = EXCLUDED.needed_reality,
                    resolution_mode = EXCLUDED.resolution_mode,
                    known_reality_reference = EXCLUDED.known_reality_reference,
                    state_hash = EXCLUDED.state_hash,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                (
                    uuid_value(need.id),
                    owner_id,
                    conversation_uuid,
                    possible_life_uuid,
                    unknown_uuid,
                    need.needed_reality,
                    need.resolution_mode.value,
                    need.known_reality_reference,
                    need.state_hash,
                    timestamp,
                    timestamp,
                ),
            ).fetchone()
            if (
                row is not None
                and need.resolution_mode != RealityNeedResolutionMode.REAL_WORLD_CONTACT
            ):
                connection.execute(
                    """
                    DELETE FROM possible_life_reality_actions
                    WHERE owner_id = %s AND reality_need_id = %s
                    """,
                    (owner_id, row["id"]),
                )
        if row is None:
            raise RuntimeError("Reality Need could not be persisted.")
        return self._from(row)

    def get(self, conversation_id: str, meaningful_unknown_id: str) -> RealityNeed | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        unknown_uuid = optional_uuid(meaningful_unknown_id)
        if owner_id is None or unknown_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM reality_needs
                WHERE owner_id = %s AND meaningful_unknown_id = %s
                """,
                (owner_id, unknown_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None


class PossibleLifeRealityActionStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _from(row: dict[str, Any]) -> PossibleLifeRealityAction:
        return PossibleLifeRealityAction(
            id=str(row["id"]),
            possible_life_id=str(row["possible_life_id"]),
            reality_need_id=str(row["reality_need_id"]),
            action_type=PossibleLifeRealityActionType(row["action_type"]),
            label=row["label"],
            why=row["why"],
            state_hash=row["state_hash"],
        )

    def save(
        self, conversation_id: str, action: PossibleLifeRealityAction,
    ) -> PossibleLifeRealityAction:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        possible_life_uuid = optional_uuid(action.possible_life_id)
        need_uuid = optional_uuid(action.reality_need_id)
        if (
            owner_id is None
            or conversation_uuid is None
            or possible_life_uuid is None
            or need_uuid is None
            or not isinstance(action.action_type, PossibleLifeRealityActionType)
            or not action.label.strip()
            or not action.why.strip()
        ):
            raise ValueError("Possible Life Reality Action is invalid.")
        timestamp = now()
        with self._database.connect() as connection:
            reference = connection.execute(
                """
                SELECT 1 FROM reality_needs AS need
                JOIN possible_lives AS possible_life
                  ON possible_life.id = need.possible_life_id
                 AND possible_life.owner_id = need.owner_id
                WHERE need.owner_id = %s AND need.id = %s
                  AND possible_life.id = %s
                  AND need.resolution_mode = 'REAL_WORLD_CONTACT'
                """,
                (owner_id, need_uuid, possible_life_uuid),
            ).fetchone()
            if reference is None:
                raise ValueError(
                    "Action requires a REAL_WORLD_CONTACT Need for the same Possible Life."
                )
            row = connection.execute(
                """
                INSERT INTO possible_life_reality_actions(
                    id, owner_id, source_conversation_id, possible_life_id,
                    reality_need_id, action_type, label, why, state_hash,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id, reality_need_id) DO UPDATE SET
                    source_conversation_id = EXCLUDED.source_conversation_id,
                    action_type = EXCLUDED.action_type,
                    label = EXCLUDED.label,
                    why = EXCLUDED.why,
                    state_hash = EXCLUDED.state_hash,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                (
                    uuid_value(action.id), owner_id, conversation_uuid,
                    possible_life_uuid, need_uuid, action.action_type.value,
                    action.label, action.why, action.state_hash,
                    timestamp, timestamp,
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("Possible Life Reality Action could not be persisted.")
        return self._from(row)

    def get(
        self, conversation_id: str, reality_need_id: str,
    ) -> PossibleLifeRealityAction | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        need_uuid = optional_uuid(reality_need_id)
        if owner_id is None or need_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM possible_life_reality_actions
                WHERE owner_id = %s AND reality_need_id = %s
                """,
                (owner_id, need_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None

    def delete(self, conversation_id: str, reality_need_id: str) -> None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        need_uuid = optional_uuid(reality_need_id)
        if owner_id is None or need_uuid is None:
            return
        with self._database.connect() as connection:
            connection.execute(
                """
                DELETE FROM possible_life_reality_actions
                WHERE owner_id = %s AND reality_need_id = %s
                """,
                (owner_id, need_uuid),
            )


class DecisionGeographyStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _from(row: dict[str, Any]) -> DecisionGeography:
        return DecisionGeography(
            intent_established=row["intent_established"],
            intent_type=row["intent_type"],
            identity=row["identity"],
            identity_source=row.get("identity_source"),
            geographic_scope=row.get("geographic_scope"),
            geographic_identity=row.get("geographic_identity"),
            geographic_precision=(
                GeographicPrecision(row["geographic_precision"])
                if row.get("geographic_precision")
                else None
            ),
            status=row["status"],
            lng=row["lng"],
            lat=row["lat"],
        )

    def get(self, conversation_id: str) -> DecisionGeography | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM decision_geographies
                WHERE owner_id = %s AND conversation_id = %s
                """,
                (owner_id, conversation_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None

    def save(self, conversation_id: str, state: DecisionGeography) -> DecisionGeography:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or conversation_uuid is None:
            raise ValueError("Conversation owner could not be resolved.")
        with self._database.connect() as connection:
            row = connection.execute(
                """
                INSERT INTO decision_geographies(
                    owner_id, conversation_id, intent_established, intent_type,
                    identity, identity_source, geographic_scope,
                    geographic_identity, geographic_precision, status, lng, lat,
                    updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id, conversation_id) DO UPDATE SET
                    intent_established = EXCLUDED.intent_established,
                    intent_type = EXCLUDED.intent_type,
                    identity = EXCLUDED.identity,
                    identity_source = EXCLUDED.identity_source,
                    geographic_scope = EXCLUDED.geographic_scope,
                    geographic_identity = EXCLUDED.geographic_identity,
                    geographic_precision = EXCLUDED.geographic_precision,
                    status = EXCLUDED.status,
                    lng = EXCLUDED.lng,
                    lat = EXCLUDED.lat,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                (
                    owner_id,
                    conversation_uuid,
                    state.intent_established,
                    state.intent_type,
                    state.identity,
                    state.identity_source,
                    state.geographic_scope,
                    state.geographic_identity,
                    state.geographic_precision.value if state.geographic_precision else None,
                    state.status,
                    state.lng,
                    state.lat,
                    now(),
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("Decision Geography could not be persisted.")
        return self._from(row)


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
            rent_source=(
                PropertyRentSource(row["rent_source"])
                if row.get("rent_source") is not None
                else None
            ),
            rent_source_reference=row.get("rent_source_reference"),
            rent_observed_at=row.get("rent_observed_at"),
            admitted_rent_evidence=row.get("admitted_rent_evidence"),
            estimated_rent_min=row.get("estimated_rent_min"),
            estimated_rent_max=row.get("estimated_rent_max"),
            rent_estimate_kind=row.get("rent_estimate_kind"),
            layout_expression=row.get("layout_expression"),
            layout_source=row.get("layout_source"),
            independent_kitchen=row.get("independent_kitchen"),
            independent_kitchen_source=row.get("independent_kitchen_source"),
            tenancy_mode=row.get("tenancy_mode"),
            tenancy_mode_source=row.get("tenancy_mode_source"),
            independent_bathroom=row.get("independent_bathroom"),
            independent_bathroom_source=row.get("independent_bathroom_source"),
            indoor_sound_observation=row.get("indoor_sound_observation"),
            indoor_sound_observation_source=row.get("indoor_sound_observation_source"),
            indoor_sound_observation_unknown=row.get("indoor_sound_observation_unknown"),
            grocery_external_id=row.get("grocery_external_id"),
            grocery_name=row.get("grocery_name"),
            grocery_identity=row.get("grocery_identity"),
            grocery_lng=row.get("grocery_lng"),
            grocery_lat=row.get("grocery_lat"),
            grocery_walking_minutes=row.get("grocery_walking_minutes"),
            place_context=row.get("place_context"),
            place_understanding=row.get("place_understanding"),
            living_meaning=row.get("living_meaning"),
            living_meaning_reality_hash=row.get("living_meaning_reality_hash"),
            current_judgment=row.get("current_judgment"),
            current_judgment_state_hash=row.get("current_judgment_state_hash"),
            decision_readiness=row.get("decision_readiness"),
            decision_readiness_reason=row.get("decision_readiness_reason"),
            decision_readiness_state_hash=row.get("decision_readiness_state_hash"),
            user_decision_expression=row.get("user_decision_expression"),
            user_decision_stance=row.get("user_decision_stance"),
            user_decision_source=row.get("user_decision_source"),
            meaningful_unknown=row.get("meaningful_unknown"),
            meaningful_unknown_why=row.get("meaningful_unknown_why"),
            meaningful_unknown_state_hash=row.get("meaningful_unknown_state_hash"),
            reality_action_type=row.get("reality_action_type"),
            reality_action_label=row.get("reality_action_label"),
            reality_action_why=row.get("reality_action_why"),
            reality_action_state_hash=row.get("reality_action_state_hash"),
            public_rent_evidence=row.get("public_rent_evidence"),
            public_action_outcome=row.get("public_action_outcome"),
            feedback_move_type=row.get("feedback_move_type"),
            feedback_move_label=row.get("feedback_move_label"),
            feedback_move_why=row.get("feedback_move_why"),
            feedback_state_hash=row.get("feedback_state_hash"),
            area=row["area"],
            bedrooms=row["bedrooms"],
            bathrooms=row["bathrooms"],
            commute_minutes=row["commute_minutes"],
            commute_mode=(
                CommuteMode(row["commute_mode"])
                if row.get("commute_mode") is not None
                else None
            ),
            pet_friendly=row["pet_friendly"],
            geographic_identity=row.get("geographic_identity"),
            geographic_precision=(
                GeographicPrecision(row["geographic_precision"])
                if row.get("geographic_precision") is not None
                else None
            ),
            geographic_status=GeographicStatus(
                row.get("geographic_status", GeographicStatus.UNRESOLVED.value)
            ),
            lng=row.get("lng"),
            lat=row.get("lat"),
            provenance=PropertyProvenance(
                row.get("provenance", PropertyProvenance.USER_PROVIDED.value)
            ),
            external_id=row.get("external_id"),
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
                    id, owner_id, conversation_id, title, district, rent, rent_source,
                    rent_source_reference, rent_observed_at,
                    grocery_external_id, grocery_name, grocery_identity,
                    grocery_lng, grocery_lat, grocery_walking_minutes,
                    living_meaning, living_meaning_reality_hash,
                    current_judgment, current_judgment_state_hash,
                    meaningful_unknown, meaningful_unknown_why,
                    meaningful_unknown_state_hash,
                    reality_action_type, reality_action_label,
                    reality_action_why, reality_action_state_hash,
                    public_rent_evidence,
                    area, bedrooms,
                    bathrooms, commute_minutes, commute_mode, pet_friendly,
                    geographic_identity,
                    geographic_precision, geographic_status, lng, lat, provenance,
                    external_id, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    uuid_value(property_.id),
                    uuid_value(owner_id),
                    optional_uuid(property_.conversation_id),
                    property_.title,
                    property_.district,
                    property_.rent,
                    property_.rent_source.value if property_.rent_source else None,
                    property_.rent_source_reference,
                    property_.rent_observed_at,
                    property_.grocery_external_id,
                    property_.grocery_name,
                    property_.grocery_identity,
                    property_.grocery_lng,
                    property_.grocery_lat,
                    property_.grocery_walking_minutes,
                    property_.living_meaning,
                    property_.living_meaning_reality_hash,
                    property_.current_judgment,
                    property_.current_judgment_state_hash,
                    property_.meaningful_unknown,
                    property_.meaningful_unknown_why,
                    property_.meaningful_unknown_state_hash,
                    property_.reality_action_type,
                    property_.reality_action_label,
                    property_.reality_action_why,
                    property_.reality_action_state_hash,
                    Jsonb(property_.public_rent_evidence)
                    if property_.public_rent_evidence is not None else None,
                    property_.area,
                    property_.bedrooms,
                    property_.bathrooms,
                    property_.commute_minutes,
                    property_.commute_mode.value if property_.commute_mode else None,
                    property_.pet_friendly,
                    property_.geographic_identity,
                    property_.geographic_precision.value
                    if property_.geographic_precision is not None
                    else None,
                    property_.geographic_status.value,
                    property_.lng,
                    property_.lat,
                    property_.provenance.value,
                    property_.external_id,
                    timestamp,
                    timestamp,
                ),
            )
        return property_

    def update_geographic_grounding(
        self,
        property_id: str,
        conversation_id: str,
        *,
        geographic_identity: str | None,
        geographic_precision: GeographicPrecision | None,
        geographic_status: GeographicStatus,
        lng: float | None,
        lat: float | None,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET geographic_identity = %s,
                    geographic_precision = %s,
                    geographic_status = %s,
                    lng = %s,
                    lat = %s,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (
                    geographic_identity,
                    geographic_precision.value if geographic_precision else None,
                    geographic_status.value,
                    lng,
                    lat,
                    now(),
                    property_uuid,
                    owner_id,
                    conversation_uuid,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_confirmed_rent(
        self,
        property_id: str,
        conversation_id: str,
        rent: int,
        source: PropertyRentSource = PropertyRentSource.USER_CONFIRMED_REALITY,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET rent = %s, rent_source = %s,
                    rent_source_reference = NULL, rent_observed_at = NULL,
                    admitted_rent_evidence = NULL,
                    estimated_rent_min = NULL, estimated_rent_max = NULL,
                    rent_estimate_kind = NULL, living_meaning = NULL,
                    living_meaning_reality_hash = NULL, current_judgment = NULL,
                    current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL, meaningful_unknown = NULL,
                    meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_rent_evidence = NULL,
                    public_action_outcome = NULL, feedback_move_type = NULL,
                    feedback_move_label = NULL, feedback_move_why = NULL,
                    feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (
                    rent,
                    source.value,
                    now(),
                    property_uuid,
                    owner_id,
                    conversation_uuid,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_external_rent(
        self,
        property_id: str,
        conversation_id: str,
        rent: int,
        *,
        source_reference: str,
        observed_at: str,
        evidence: dict,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET rent = %s, rent_source = %s, rent_source_reference = %s,
                    rent_observed_at = %s, admitted_rent_evidence = %s,
                    estimated_rent_min = NULL, estimated_rent_max = NULL,
                    rent_estimate_kind = NULL, living_meaning = NULL,
                    living_meaning_reality_hash = NULL, current_judgment = NULL,
                    current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL, meaningful_unknown = NULL,
                    meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_rent_evidence = NULL,
                    public_action_outcome = NULL, feedback_move_type = NULL,
                    feedback_move_label = NULL, feedback_move_why = NULL,
                    feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (
                    rent,
                    PropertyRentSource.EXTERNAL_SOURCE.value,
                    source_reference,
                    observed_at,
                    Jsonb(evidence),
                    now(),
                    property_uuid,
                    owner_id,
                    conversation_uuid,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_controlled_rent_estimate(
        self,
        property_id: str,
        conversation_id: str,
        *,
        minimum_monthly: int,
        maximum_monthly: int,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET estimated_rent_min = %s, estimated_rent_max = %s,
                    rent_estimate_kind = 'CONTROLLED_ESTIMATE',
                    living_meaning = NULL, living_meaning_reality_hash = NULL,
                    current_judgment = NULL, current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL,
                    meaningful_unknown = NULL, meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_action_outcome = NULL,
                    feedback_move_type = NULL, feedback_move_label = NULL,
                    feedback_move_why = NULL, feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND rent IS NULL
                RETURNING *
                """,
                (
                    minimum_monthly,
                    maximum_monthly,
                    now(),
                    property_uuid,
                    owner_id,
                    conversation_uuid,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def admit_user_layout_reality(
        self, property_id: str, conversation_id: str, *,
        expression: str,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if (
            owner_id is None or property_uuid is None or conversation_uuid is None
            or not expression.strip() or len(expression) > 60
        ):
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET layout_expression = %s, layout_source = 'USER_PROVIDED',
                    living_meaning = NULL, living_meaning_reality_hash = NULL,
                    current_judgment = NULL, current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL,
                    meaningful_unknown = NULL, meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_rent_evidence = NULL, public_action_outcome = NULL,
                    feedback_move_type = NULL, feedback_move_label = NULL,
                    feedback_move_why = NULL, feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND geographic_status = 'GROUNDED'
                  AND layout_expression IS DISTINCT FROM %s
                RETURNING *
                """,
                (expression, now(), property_uuid, owner_id,
                 conversation_uuid, expression),
            ).fetchone()
        return self._from(row) if row is not None else None

    def admit_user_bathroom_reality(
        self, property_id: str, conversation_id: str, *,
        unknown_hash: str, independent_bathroom: bool,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if (
            owner_id is None or property_uuid is None or conversation_uuid is None
            or type(independent_bathroom) is not bool
        ):
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET independent_bathroom = %s, independent_bathroom_source = 'USER_PROVIDED',
                    living_meaning = NULL, living_meaning_reality_hash = NULL,
                    current_judgment = NULL, current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL,
                    meaningful_unknown = NULL, meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_rent_evidence = NULL, public_action_outcome = NULL,
                    feedback_move_type = NULL, feedback_move_label = NULL,
                    feedback_move_why = NULL, feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND meaningful_unknown_state_hash = %s
                  AND meaningful_unknown IS NOT NULL
                  AND geographic_status = 'GROUNDED'
                  AND independent_bathroom IS NULL
                RETURNING *
                """,
                (independent_bathroom, now(), property_uuid, owner_id,
                 conversation_uuid, unknown_hash),
            ).fetchone()
        return self._from(row) if row is not None else None

    def admit_user_tenancy_reality(
        self, property_id: str, conversation_id: str, *,
        unknown_hash: str, tenancy_mode: str,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if (
            owner_id is None or property_uuid is None or conversation_uuid is None
            or tenancy_mode not in {"ENTIRE_RENT", "SHARED_RENT"}
        ):
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET tenancy_mode = %s, tenancy_mode_source = 'USER_PROVIDED',
                    living_meaning = NULL, living_meaning_reality_hash = NULL,
                    current_judgment = NULL, current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL,
                    meaningful_unknown = NULL, meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_rent_evidence = NULL, public_action_outcome = NULL,
                    feedback_move_type = NULL, feedback_move_label = NULL,
                    feedback_move_why = NULL, feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND meaningful_unknown_state_hash = %s
                  AND meaningful_unknown IS NOT NULL
                  AND geographic_status = 'GROUNDED'
                  AND tenancy_mode IS NULL
                RETURNING *
                """,
                (tenancy_mode, now(), property_uuid, owner_id,
                 conversation_uuid, unknown_hash),
            ).fetchone()
        return self._from(row) if row is not None else None

    def admit_user_kitchen_reality(
        self, property_id: str, conversation_id: str, *,
        unknown_hash: str, kitchen_present: bool,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET independent_kitchen = %s,
                    independent_kitchen_source = 'USER_PROVIDED',
                    living_meaning = NULL, living_meaning_reality_hash = NULL,
                    current_judgment = NULL, current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL,
                    meaningful_unknown = NULL, meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_rent_evidence = NULL, public_action_outcome = NULL,
                    feedback_move_type = NULL, feedback_move_label = NULL,
                    feedback_move_why = NULL, feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND meaningful_unknown_state_hash = %s
                  AND meaningful_unknown IS NOT NULL
                  AND (reality_action_type = 'USER_REALITY'
                       OR feedback_move_type = 'USER_REALITY')
                  AND independent_kitchen IS NULL
                RETURNING *
                """,
                (kitchen_present, now(), property_uuid, owner_id,
                 conversation_uuid, unknown_hash),
            ).fetchone()
        return self._from(row) if row is not None else None

    def admit_user_sound_observation(
        self, property_id: str, conversation_id: str, *,
        unknown_hash: str, unknown_question: str, observation: str,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET indoor_sound_observation = %s,
                    indoor_sound_observation_source = 'USER_PROVIDED',
                    indoor_sound_observation_unknown = %s,
                    living_meaning = NULL, living_meaning_reality_hash = NULL,
                    current_judgment = NULL, current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL,
                    meaningful_unknown = NULL, meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_rent_evidence = NULL, public_action_outcome = NULL,
                    feedback_move_type = NULL, feedback_move_label = NULL,
                    feedback_move_why = NULL, feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND meaningful_unknown_state_hash = %s
                  AND meaningful_unknown = %s
                  AND (reality_action_type = 'USER_REALITY'
                       OR feedback_move_type = 'USER_REALITY')
                  AND indoor_sound_observation IS NULL
                RETURNING *
                """,
                (observation, unknown_question, now(), property_uuid,
                 owner_id, conversation_uuid, unknown_hash, unknown_question),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_daily_grocery(
        self,
        property_id: str,
        conversation_id: str,
        *,
        external_id: str,
        name: str,
        identity: str,
        lng: float,
        lat: float,
        walking_minutes: int,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET grocery_external_id = %s, grocery_name = %s,
                    grocery_identity = %s, grocery_lng = %s, grocery_lat = %s,
                    grocery_walking_minutes = %s, living_meaning = NULL,
                    living_meaning_reality_hash = NULL, current_judgment = NULL,
                    current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL, meaningful_unknown = NULL,
                    meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_rent_evidence = NULL,
                    public_action_outcome = NULL, feedback_move_type = NULL,
                    feedback_move_label = NULL, feedback_move_why = NULL,
                    feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (
                    external_id,
                    name,
                    identity,
                    lng,
                    lat,
                    walking_minutes,
                    now(),
                    property_uuid,
                    owner_id,
                    conversation_uuid,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_place_context(
        self, property_id: str, conversation_id: str, items: list[dict],
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET place_context = %s, place_understanding = NULL, updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (
                    Jsonb(items), now(), property_uuid, owner_id,
                    conversation_uuid,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_place_understanding(
        self, property_id: str, conversation_id: str, understanding: dict,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET place_understanding = %s, updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (Jsonb(understanding), now(), property_uuid, owner_id, conversation_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_living_meaning(
        self,
        property_id: str,
        conversation_id: str,
        *,
        meaning: str | None,
        reality_hash: str | None,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET living_meaning = %s, living_meaning_reality_hash = %s,
                    current_judgment = NULL, current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL,
                    meaningful_unknown = NULL, meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_action_outcome = NULL, feedback_move_type = NULL,
                    feedback_move_label = NULL, feedback_move_why = NULL,
                    feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (
                    meaning,
                    reality_hash,
                    now(),
                    property_uuid,
                    owner_id,
                    conversation_uuid,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_current_judgment(
        self,
        property_id: str,
        conversation_id: str,
        *,
        judgment: str,
        state_hash: str,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET current_judgment = %s, current_judgment_state_hash = %s,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL,
                    meaningful_unknown = NULL, meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_action_outcome = NULL, feedback_move_type = NULL,
                    feedback_move_label = NULL, feedback_move_why = NULL,
                    feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (
                    judgment,
                    state_hash,
                    now(),
                    property_uuid,
                    owner_id,
                    conversation_uuid,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_decision_readiness(
        self, property_id: str, conversation_id: str, *,
        status: str, reason: str, state_hash: str, judgment_hash: str,
    ) -> Property | None:
        if status not in {"NEED_MORE_REALITY", "DECISION_READY"}:
            return None
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET decision_readiness = %s, decision_readiness_reason = %s,
                    decision_readiness_state_hash = %s,
                    meaningful_unknown = NULL, meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_action_outcome = NULL,
                    feedback_move_type = NULL, feedback_move_label = NULL,
                    feedback_move_why = NULL, feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND current_judgment_state_hash = %s
                RETURNING *
                """,
                (status, reason, state_hash, now(), property_uuid,
                 owner_id, conversation_uuid, judgment_hash),
            ).fetchone()
        return self._from(row) if row is not None else None

    def admit_user_decision(
        self, property_id: str, conversation_id: str, *,
        readiness_hash: str, expression: str, stance: str,
    ) -> Property | None:
        if stance not in {"ACCEPT", "DECLINE"} or not expression.strip():
            return None
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET user_decision_expression = %s, user_decision_stance = %s,
                    user_decision_source = 'USER_PROVIDED', updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND geographic_status = 'GROUNDED'
                  AND decision_readiness = 'DECISION_READY'
                  AND decision_readiness_state_hash = %s
                  AND user_decision_expression IS NULL
                RETURNING *
                """,
                (expression.strip(), stance, now(), property_uuid, owner_id,
                 conversation_uuid, readiness_hash),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_meaningful_unknown(
        self,
        property_id: str,
        conversation_id: str,
        *,
        question: str,
        why: str,
        state_hash: str,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET meaningful_unknown = %s, meaningful_unknown_why = %s,
                    meaningful_unknown_state_hash = %s,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_action_outcome = NULL, feedback_move_type = NULL,
                    feedback_move_label = NULL, feedback_move_why = NULL,
                    feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (
                    question,
                    why,
                    state_hash,
                    now(),
                    property_uuid,
                    owner_id,
                    conversation_uuid,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_reality_action(
        self,
        property_id: str,
        conversation_id: str,
        *,
        action_type: str,
        label: str,
        why: str,
        state_hash: str,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET reality_action_type = %s, reality_action_label = %s,
                    reality_action_why = %s, reality_action_state_hash = %s,
                    public_action_outcome = NULL, feedback_move_type = NULL,
                    feedback_move_label = NULL, feedback_move_why = NULL,
                    feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (
                    action_type, label, why, state_hash, now(),
                    property_uuid, owner_id, conversation_uuid,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_public_rent_evidence(
        self, property_id: str, conversation_id: str, *, action_hash: str,
        evidence: dict,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties SET public_rent_evidence = %s,
                    public_action_outcome = NULL, feedback_move_type = NULL,
                    feedback_move_label = NULL, feedback_move_why = NULL,
                    feedback_state_hash = NULL, updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND reality_action_type = 'PUBLIC_EVIDENCE'
                  AND reality_action_state_hash = %s AND rent IS NULL
                RETURNING *
                """,
                (Jsonb(evidence), now(), property_uuid, owner_id,
                 conversation_uuid, action_hash),
            ).fetchone()
        return self._from(row) if row is not None else None

    def record_public_action_no_evidence(
        self, property_id: str, conversation_id: str, *, action_hash: str,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties SET public_action_outcome = 'NO_EVIDENCE',
                    feedback_move_type = NULL, feedback_move_label = NULL,
                    feedback_move_why = NULL, feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND reality_action_type = 'PUBLIC_EVIDENCE'
                  AND reality_action_state_hash = %s
                  AND (public_rent_evidence IS NULL OR public_rent_evidence = 'null'::jsonb)
                  AND rent IS NULL
                RETURNING *
                """,
                (now(), property_uuid, owner_id, conversation_uuid, action_hash),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_public_rent_understanding(
        self, property_id: str, conversation_id: str, *, action_hash: str,
        source_reference: str, understanding: dict,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET public_rent_evidence = public_rent_evidence || %s,
                    living_meaning = NULL, living_meaning_reality_hash = NULL,
                    current_judgment = NULL, current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL, updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND reality_action_type = 'PUBLIC_EVIDENCE'
                  AND reality_action_state_hash = %s AND rent IS NULL
                  AND public_rent_evidence->>'source_reference' = %s
                RETURNING *
                """,
                (
                    Jsonb({"understanding": understanding}), now(), property_uuid,
                    owner_id, conversation_uuid, action_hash, source_reference,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_action_feedback(
        self, property_id: str, conversation_id: str, *, action_hash: str,
        move_type: str, label: str, why: str, state_hash: str,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties SET feedback_move_type = %s,
                    feedback_move_label = %s, feedback_move_why = %s,
                    feedback_state_hash = %s, updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                  AND reality_action_type = 'PUBLIC_EVIDENCE'
                  AND reality_action_state_hash = %s
                  AND public_action_outcome = 'NO_EVIDENCE'
                  AND (public_rent_evidence IS NULL OR public_rent_evidence = 'null'::jsonb)
                  AND rent IS NULL
                RETURNING *
                """,
                (move_type, label, why, state_hash, now(), property_uuid,
                 owner_id, conversation_uuid, action_hash),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_commute_minutes(
        self,
        property_id: str,
        conversation_id: str,
        commute_minutes: int | None,
        commute_mode: CommuteMode | None = None,
    ) -> Property | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        property_uuid = optional_uuid(property_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or property_uuid is None or conversation_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE properties
                SET commute_minutes = %s, commute_mode = %s,
                    living_meaning = NULL, living_meaning_reality_hash = NULL,
                    current_judgment = NULL, current_judgment_state_hash = NULL,
                    decision_readiness = NULL, decision_readiness_reason = NULL,
                    decision_readiness_state_hash = NULL,
                    meaningful_unknown = NULL, meaningful_unknown_why = NULL,
                    meaningful_unknown_state_hash = NULL,
                    reality_action_type = NULL, reality_action_label = NULL,
                    reality_action_why = NULL, reality_action_state_hash = NULL,
                    public_rent_evidence = NULL,
                    public_action_outcome = NULL, feedback_move_type = NULL,
                    feedback_move_label = NULL, feedback_move_why = NULL,
                    feedback_state_hash = NULL,
                    updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (
                    commute_minutes,
                    commute_mode.value if commute_mode else None,
                    now(),
                    property_uuid,
                    owner_id,
                    conversation_uuid,
                ),
            ).fetchone()
        return self._from(row) if row is not None else None

    def list(self, conversation_id: str) -> list[Property]:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        if owner_id is None or conversation_uuid is None:
            return []
        with self._database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM properties
                WHERE owner_id = %s AND conversation_id = %s
                ORDER BY created_at
                """,
                (owner_id, conversation_uuid),
            ).fetchall()
        return [self._from(row) for row in rows]

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


class DecisionUnknownStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    @staticmethod
    def _from(row: dict[str, Any]) -> DecisionUnknown:
        return DecisionUnknown(
            id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            property_id=str(row["property_id"]),
            topic=row["topic"],
            status=DecisionUnknownStatus(row["status"]),
            meaning=row["meaning"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def upsert_open(self, unknown: DecisionUnknown) -> DecisionUnknown:
        owner_id = resolve_owner_id(self._database, unknown.conversation_id)
        conversation_id = optional_uuid(unknown.conversation_id)
        property_id = optional_uuid(unknown.property_id)
        if owner_id is None or conversation_id is None or property_id is None:
            raise ValueError("Decision Unknown requires valid Conversation and Property IDs.")
        if unknown.status != DecisionUnknownStatus.OPEN:
            raise ValueError("Only OPEN Decision Unknowns can be created.")

        with self._database.connect() as connection:
            property_row = connection.execute(
                "SELECT id FROM properties WHERE id = %s AND owner_id = %s",
                (property_id, owner_id),
            ).fetchone()
            if property_row is None:
                raise ValueError("Decision Unknown Property does not belong to Owner.")

            row = connection.execute(
                """
                INSERT INTO decision_unknowns(
                    id, owner_id, conversation_id, property_id, topic, status,
                    meaning, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, 'OPEN', %s, %s, %s)
                ON CONFLICT (owner_id, conversation_id, property_id, topic)
                    WHERE status = 'OPEN'
                DO UPDATE SET
                    meaning = EXCLUDED.meaning,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                (
                    uuid_value(unknown.id),
                    owner_id,
                    conversation_id,
                    property_id,
                    unknown.topic,
                    unknown.meaning,
                    unknown.created_at,
                    unknown.updated_at,
                ),
            ).fetchone()
        if row is None:
            raise RuntimeError("Decision Unknown could not be stored.")
        return self._from(row)

    def list_open(
        self,
        conversation_id: str,
        property_id: str | None = None,
    ) -> list[DecisionUnknown]:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        property_uuid = optional_uuid(property_id) if property_id is not None else None
        if owner_id is None or conversation_uuid is None:
            return []
        if property_id is not None and property_uuid is None:
            return []

        query = """
            SELECT * FROM decision_unknowns
            WHERE owner_id = %s AND conversation_id = %s AND status = 'OPEN'
        """
        values: tuple[object, ...] = (owner_id, conversation_uuid)
        if property_uuid is not None:
            query += " AND property_id = %s"
            values = (*values, property_uuid)
        query += " ORDER BY created_at, id"

        with self._database.connect() as connection:
            rows = connection.execute(query, values).fetchall()
        return [self._from(row) for row in rows]

    def get_for_conversation(
        self,
        conversation_id: str,
        unknown_id: str,
    ) -> DecisionUnknown | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        unknown_uuid = optional_uuid(unknown_id)
        if owner_id is None or conversation_uuid is None or unknown_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM decision_unknowns
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                """,
                (unknown_uuid, owner_id, conversation_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None

    def update_status(
        self,
        conversation_id: str,
        unknown_id: str,
        status: DecisionUnknownStatus,
    ) -> DecisionUnknown | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        unknown_uuid = optional_uuid(unknown_id)
        if owner_id is None or conversation_uuid is None or unknown_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE decision_unknowns
                SET status = %s, updated_at = %s
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (status.value, now(), unknown_uuid, owner_id, conversation_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None


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
                    reasons_json, trade_offs_json, confidence, decision_gap,
                    recommendation_invalidated
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    record.recommendation_invalidated,
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
            recommendation_invalidated=row.get("recommendation_invalidated", False),
        )

    def invalidate_recommendation(
        self,
        conversation_id: str,
        record_id: str,
    ) -> DecisionRecord | None:
        owner_id = resolve_owner_id(self._database, conversation_id)
        conversation_uuid = optional_uuid(conversation_id)
        record_uuid = optional_uuid(record_id)
        if owner_id is None or conversation_uuid is None or record_uuid is None:
            return None
        with self._database.connect() as connection:
            row = connection.execute(
                """
                UPDATE decision_records
                SET recommendation_invalidated = TRUE
                WHERE id = %s AND owner_id = %s AND conversation_id = %s
                RETURNING *
                """,
                (record_uuid, owner_id, conversation_uuid),
            ).fetchone()
        return self._from(row) if row is not None else None

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
                    unknown_id, action_key, next_text, status, outcome_status,
                    verification_evidence_json, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id, conversation_id) DO UPDATE SET
                    id = EXCLUDED.id,
                    decision_record_id = EXCLUDED.decision_record_id,
                    unknown_id = EXCLUDED.unknown_id,
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
                    uuid_value(state.unknown_id) if state.unknown_id is not None else None,
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
            unknown_id=(str(row["unknown_id"]) if row["unknown_id"] is not None else None),
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
                    unknown_id, action_key, next_text, status, outcome_status,
                    verification_evidence_json, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (owner_id, conversation_id) DO UPDATE SET
                    action_id = EXCLUDED.action_id,
                    decision_record_id = EXCLUDED.decision_record_id,
                    unknown_id = EXCLUDED.unknown_id,
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
                    uuid_value(action.unknown_id) if action.unknown_id is not None else None,
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
            unknown_id=(str(row["unknown_id"]) if row["unknown_id"] is not None else None),
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
