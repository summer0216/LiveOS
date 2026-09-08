from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from app.models.property import GeographicPrecision, GeographicStatus, Property
from app.services.conversation_manager import conversation_manager
from app.services.geographic_resolution import (
    GeographicResolutionResult,
    geographic_resolver,
)
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

    def materialize_choices(
        self,
        conversation_id: str,
        choices: list[Property],
    ) -> list[Property]:
        """Persist explicit conversation choices once per conversation/title."""
        existing = self.list(conversation_id)
        by_title = {
            "".join((property_.title or "").split()).casefold(): property_
            for property_ in existing
            if property_.title and property_.title.strip()
        }
        materialized: list[Property] = []
        for choice in choices:
            title = (choice.title or "").strip()
            key = "".join(title.split()).casefold()
            if not key:
                continue
            current = by_title.get(key)
            if current is None:
                current = self.create(
                    conversation_id=conversation_id,
                    property_=replace(choice, title=title),
                )
                by_title[key] = current
            materialized.append(current)
        return materialized

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
        return property_store.update_geographic_grounding(
            property_id,
            conversation_id,
            geographic_identity=geographic_identity,
            geographic_precision=geographic_precision,
            geographic_status=geographic_status,
            lng=lng,
            lat=lat,
        )

    def resolve_geographic_grounding(
        self,
        property_id: str,
        conversation_id: str,
        *,
        context_location: str | None,
        api_key: str | None,
    ) -> GeographicResolutionResult:
        property_ = next(
            (item for item in self.list(conversation_id) if item.id == property_id),
            None,
        )
        if property_ is None or not property_.title:
            return GeographicResolutionResult(status="UNRESOLVED")

        result = geographic_resolver.resolve(
            property_.title,
            context_location,
            api_key,
        )
        if result.status == "GROUNDED":
            self.update_geographic_grounding(
                property_id,
                conversation_id,
                geographic_identity=result.geographic_identity,
                geographic_precision=result.geographic_precision,
                geographic_status=GeographicStatus.GROUNDED,
                lng=result.lng,
                lat=result.lat,
            )
        return result

    def get_scoped(self, property_id: str, conversation_id: str) -> Property | None:
        return next(
            (item for item in self.list(conversation_id) if item.id == property_id),
            None,
        )

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
