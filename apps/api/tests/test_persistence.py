import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.models.profile import LivingProfile
from app.models.property import Property
from app.schemas.decision import DecisionReason, DecisionTradeOff
from app.schemas.decision_record import DecisionRecord
from app.stores.database import Database
from app.stores.persistent import (
    ConversationStore,
    DecisionRecordStore,
    ProfileStore,
    PropertyStore,
)


def test_sqlite_runtime_data_survives_database_reopen(tmp_path: Path) -> None:
    database_path = str(tmp_path / "liveos-test.db")
    database = Database(database_path)
    database.initialize()

    conversation_id = "persisted-conversation"
    user_id = "persisted-user"
    conversation_store = ConversationStore(database)
    profile_store = ProfileStore(database)
    property_store = PropertyStore(database)
    record_store = DecisionRecordStore(database)

    conversation_store.get_or_create(conversation_id, user_id)
    conversation_store.append(conversation_id, "user", "寻找通勤方便的房源")
    profile_store.save(
        conversation_id,
        LivingProfile(work_location="南山", budget=6000, has_pet=False),
    )
    property_ = property_store.create(
        Property(
            id="persisted-property",
            conversation_id=conversation_id,
            title="候选房源",
            rent=5800,
        )
    )
    record = record_store.save(
        DecisionRecord(
            id="persisted-record",
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
    timestamp = datetime.now(UTC).isoformat()
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO decision_memories VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(memory_id),
                conversation_id,
                "priority",
                "持续优先考虑通勤。",
                "持续优先考虑通勤。",
                0.9,
                json.dumps([str(uuid4())]),
                timestamp,
                timestamp,
            ),
        )

    reopened_database = Database(database_path)
    reopened_database.initialize()
    reopened_conversations = ConversationStore(reopened_database)
    reopened_profiles = ProfileStore(reopened_database)
    reopened_properties = PropertyStore(reopened_database)
    reopened_records = DecisionRecordStore(reopened_database)

    conversation = reopened_conversations.get(conversation_id)
    assert conversation is not None
    assert [message.content for message in conversation.get_messages()] == [
        "寻找通勤方便的房源"
    ]
    persisted_profile = reopened_profiles.get(conversation_id)
    assert persisted_profile is not None
    assert persisted_profile.budget == 6000
    assert [item.id for item in reopened_properties.list(conversation_id)] == [
        property_.id
    ]
    assert [
        item.id for item in reopened_records.list_by_conversation(conversation_id)
    ] == [record.id]
    with reopened_database.connect() as connection:
        persisted_memory = connection.execute(
            "SELECT id FROM decision_memories WHERE id = ?", (str(memory_id),)
        ).fetchone()
    assert persisted_memory is not None
