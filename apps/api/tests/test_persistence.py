from datetime import UTC, datetime
from uuid import uuid4

import pytest
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from app.core.config import settings
from app.models.decision_memory import DecisionMemory, DecisionMemoryCategory
from app.models.profile import LivingProfile
from app.models.property import Property
from app.schemas.decision import DecisionReason, DecisionTradeOff
from app.schemas.decision_record import DecisionRecord
from app.stores.database import Database
from app.stores.decision_memory_store import decision_memory_store
from app.stores.persistent import (
    ConversationStore,
    DecisionRecordStore,
    ProfileStore,
    PropertyStore,
)
from tests.ids import uuid_for


def test_postgresql_runtime_data_survives_database_reconnect() -> None:
    database = Database(settings.DATABASE_URL)
    database.initialize()

    conversation_id = uuid_for("persisted-conversation")
    user_id = uuid_for("persisted-user")
    property_id = uuid_for("persisted-property")
    record_id = uuid_for("persisted-record")
    conversation_store = ConversationStore(database)
    profile_store = ProfileStore(database)
    property_store = PropertyStore(database)
    record_store = DecisionRecordStore(database)

    conversation_store.delete(conversation_id)
    conversation_store.get_or_create(conversation_id, user_id)
    conversation_store.append(conversation_id, "user", "寻找通勤方便的房源")
    profile_store.save(
        conversation_id,
        LivingProfile(work_location="南山", budget=6000, has_pet=False),
    )
    property_ = property_store.create(
        Property(
            id=property_id,
            conversation_id=conversation_id,
            title="候选房源",
            rent=5800,
        )
    )
    record = record_store.save(
        DecisionRecord(
            id=record_id,
            conversation_id=conversation_id,
            created_at=datetime.now(UTC),
            summary="保存的决策快照",
            best_property_id=property_.id or "",
            reasons=[DecisionReason(title="预算", description="符合预算")],
            trade_offs=[DecisionTradeOff(title="面积", description="需要取舍")],
            confidence=0.8,
        )
    )
    memory_id = uuid4()
    timestamp = datetime.now(UTC)
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO decision_memories(
                id, conversation_id, category, content, normalized_content,
                confidence, evidence_record_ids_json, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                memory_id,
                conversation_id,
                "priority",
                "持续优先考虑通勤。",
                "持续优先考虑通勤。",
                0.9,
                Jsonb([str(uuid4())]),
                timestamp,
                timestamp,
            ),
        )

    reconnected_database = Database(settings.DATABASE_URL)
    reconnected_database.initialize()
    reconnected_conversations = ConversationStore(reconnected_database)
    reconnected_profiles = ProfileStore(reconnected_database)
    reconnected_properties = PropertyStore(reconnected_database)
    reconnected_records = DecisionRecordStore(reconnected_database)

    conversation = reconnected_conversations.get(conversation_id)
    assert conversation is not None
    assert [message.content for message in conversation.get_messages()] == [
        "寻找通勤方便的房源"
    ]
    persisted_profile = reconnected_profiles.get(conversation_id)
    assert persisted_profile is not None
    assert persisted_profile.budget == 6000
    assert [item.id for item in reconnected_properties.list(conversation_id)] == [
        property_.id
    ]
    assert [
        item.id for item in reconnected_records.list_by_conversation(conversation_id)
    ] == [record.id]
    with reconnected_database.connect() as connection:
        persisted_memory = connection.execute(
            "SELECT id FROM decision_memories WHERE id = %s", (memory_id,)
        ).fetchone()
    assert persisted_memory is not None

    reconnected_conversations.delete(conversation_id)


def test_postgresql_memory_replace_rolls_back_as_one_transaction() -> None:
    database = Database(settings.DATABASE_URL)
    conversation_id = uuid_for("atomic-memory-conversation")
    user_id = uuid_for("atomic-memory-user")
    conversation_store = ConversationStore(database)
    conversation_store.delete(conversation_id)
    conversation_store.get_or_create(conversation_id, user_id)
    timestamp = datetime.now(UTC)
    original = DecisionMemory(
        id=uuid4(),
        conversation_id=conversation_id,
        category=DecisionMemoryCategory.PRIORITY,
        content="原始记忆",
        normalized_content="原始记忆",
        confidence=0.8,
        evidence_record_ids=[uuid4(), uuid4()],
        created_at=timestamp,
        updated_at=timestamp,
    )
    decision_memory_store.save(original)

    duplicate_id = uuid4()
    replacements = [
        original.model_copy(
            update={
                "id": duplicate_id,
                "content": f"替换记忆 {index}",
                "normalized_content": f"替换记忆 {index}",
            }
        )
        for index in range(2)
    ]

    with pytest.raises(UniqueViolation):
        decision_memory_store.replace_conversation(
            conversation_id,
            replacements,
        )

    assert decision_memory_store.list_by_conversation(conversation_id) == [original]
    conversation_store.delete(conversation_id)
