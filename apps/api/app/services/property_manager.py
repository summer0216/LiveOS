from dataclasses import replace
from uuid import uuid4

from app.models.property import Property
from app.services.conversation_manager import conversation_manager
from app.stores.runtime import property_store


class PropertyManager:
    def create(
        self,
        conversation_id: str,
        property_: Property,
    ) -> Property:
        stored_property = replace(
            property_,
            id=str(uuid4()),
            conversation_id=conversation_id,
        )
        conversation_manager.get_or_create(conversation_id)
        return property_store.create(stored_property)

    def list(
        self,
        conversation_id: str,
    ) -> list[Property]:
        return property_store.list(conversation_id)

    def get(
        self,
        conversation_id: str,
    ) -> Property | None:
        properties = property_store.list(conversation_id)
        return properties[-1] if properties else None

    def delete(
        self,
        property_id: str,
    ) -> bool:
        return property_store.delete(property_id)

    def delete_scoped(self, property_id: str, conversation_id: str) -> bool:
        return property_store.delete(property_id, conversation_id)

    def delete_for_owner(self, property_id: str, user_id: str) -> bool:
        return property_store.delete_for_owner(property_id, user_id)

    def delete_conversation(
        self,
        conversation_id: str,
    ) -> None:
        property_store.delete_conversation(conversation_id)


property_manager = PropertyManager()
