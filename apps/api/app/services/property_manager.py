from dataclasses import replace
from uuid import uuid4

from app.models.property import Property


class PropertyManager:
    def __init__(self) -> None:
        self._properties: dict[str, list[Property]] = {}

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
        self._properties.setdefault(
            conversation_id,
            [],
        ).append(stored_property)

        return stored_property

    def list(
        self,
        conversation_id: str,
    ) -> list[Property]:
        return list(
            self._properties.get(
                conversation_id,
                [],
            ),
        )

    def get(
        self,
        conversation_id: str,
    ) -> Property | None:
        properties = self._properties.get(
            conversation_id,
            [],
        )

        return properties[-1] if properties else None

    def delete(
        self,
        property_id: str,
    ) -> bool:
        for conversation_id, properties in list(
            self._properties.items(),
        ):
            remaining_properties = [
                property_
                for property_ in properties
                if property_.id != property_id
            ]

            if len(remaining_properties) == len(properties):
                continue

            if remaining_properties:
                self._properties[conversation_id] = remaining_properties
            else:
                self._properties.pop(conversation_id)

            return True

        return False

    def delete_conversation(
        self,
        conversation_id: str,
    ) -> None:
        self._properties.pop(conversation_id, None)


property_manager = PropertyManager()
