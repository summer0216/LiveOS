from app.models.property import Property


class PropertyManager:
    def __init__(self) -> None:
        self._properties: dict[str, Property] = {}

    def set(
        self,
        conversation_id: str,
        property_: Property,
    ) -> Property:
        self._properties[conversation_id] = property_

        return property_

    def get(
        self,
        conversation_id: str,
    ) -> Property | None:
        return self._properties.get(conversation_id)

    def delete(
        self,
        conversation_id: str,
    ) -> None:
        self._properties.pop(conversation_id, None)


property_manager = PropertyManager()
