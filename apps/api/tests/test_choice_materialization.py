from app.models.property import Property
from app.services.conversation_manager import conversation_manager
from app.services.property_manager import property_manager


def test_materialize_choices_is_idempotent_and_conversation_scoped() -> None:
    conversation_id = "00000000-0000-0000-0000-00000000c016"
    conversation_manager.get_or_create(conversation_id)
    choices = [
        Property(title="候选一", commute_minutes=24),
        Property(title="候选二", commute_minutes=31),
    ]

    first = property_manager.materialize_choices(conversation_id, choices)
    second = property_manager.materialize_choices(conversation_id, choices)

    assert [item.id for item in first] == [item.id for item in second]
    assert len(property_manager.list(conversation_id)) == 2
    assert all(item.conversation_id == conversation_id for item in first)
