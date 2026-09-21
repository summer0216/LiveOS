from __future__ import annotations

from dataclasses import replace
from uuid import uuid4

from app.models.property import (
    CommuteMode,
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyRentSource,
)
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

    def update_commute_minutes(
        self,
        property_id: str,
        conversation_id: str,
        commute_minutes: int | None,
        commute_mode: CommuteMode | None = None,
    ) -> Property | None:
        return property_store.update_commute_minutes(
            property_id,
            conversation_id,
            commute_minutes,
            commute_mode,
        )

    def update_confirmed_rent(
        self,
        property_id: str,
        conversation_id: str,
        rent: int,
        source: PropertyRentSource = PropertyRentSource.USER_CONFIRMED_REALITY,
    ) -> Property | None:
        return property_store.update_confirmed_rent(
            property_id,
            conversation_id,
            rent,
            source,
        )

    def update_external_rent(
        self,
        property_id: str,
        conversation_id: str,
        rent: int,
        *,
        source_reference: str,
        observed_at: str,
    ) -> Property | None:
        return property_store.update_external_rent(
            property_id,
            conversation_id,
            rent,
            source_reference=source_reference,
            observed_at=observed_at,
        )

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
        return property_store.update_daily_grocery(
            property_id,
            conversation_id,
            external_id=external_id,
            name=name,
            identity=identity,
            lng=lng,
            lat=lat,
            walking_minutes=walking_minutes,
        )

    def admit_user_kitchen_reality(
        self, property_id: str, conversation_id: str, *,
        unknown_hash: str, kitchen_present: bool,
    ) -> Property | None:
        return property_store.admit_user_kitchen_reality(
            property_id, conversation_id, unknown_hash=unknown_hash,
            kitchen_present=kitchen_present,
        )

    def admit_user_sound_observation(
        self, property_id: str, conversation_id: str, *,
        unknown_hash: str, unknown_question: str, observation: str,
    ) -> Property | None:
        return property_store.admit_user_sound_observation(
            property_id, conversation_id, unknown_hash=unknown_hash,
            unknown_question=unknown_question, observation=observation,
        )

    def update_living_meaning(
        self,
        property_id: str,
        conversation_id: str,
        *,
        meaning: str,
        reality_hash: str,
    ) -> Property | None:
        return property_store.update_living_meaning(
            property_id,
            conversation_id,
            meaning=meaning,
            reality_hash=reality_hash,
        )

    def update_current_judgment(
        self,
        property_id: str,
        conversation_id: str,
        *,
        judgment: str,
        state_hash: str,
    ) -> Property | None:
        return property_store.update_current_judgment(
            property_id,
            conversation_id,
            judgment=judgment,
            state_hash=state_hash,
        )

    def update_decision_readiness(
        self, property_id: str, conversation_id: str, *,
        status: str, reason: str, state_hash: str, judgment_hash: str,
    ) -> Property | None:
        return property_store.update_decision_readiness(
            property_id, conversation_id, status=status, reason=reason,
            state_hash=state_hash, judgment_hash=judgment_hash,
        )

    def admit_user_decision(
        self, property_id: str, conversation_id: str, *,
        readiness_hash: str, expression: str, stance: str,
    ) -> Property | None:
        return property_store.admit_user_decision(
            property_id, conversation_id, readiness_hash=readiness_hash,
            expression=expression, stance=stance,
        )

    def update_meaningful_unknown(
        self,
        property_id: str,
        conversation_id: str,
        *,
        question: str,
        why: str,
        state_hash: str,
    ) -> Property | None:
        return property_store.update_meaningful_unknown(
            property_id,
            conversation_id,
            question=question,
            why=why,
            state_hash=state_hash,
        )

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
        return property_store.update_reality_action(
            property_id,
            conversation_id,
            action_type=action_type,
            label=label,
            why=why,
            state_hash=state_hash,
        )

    def update_public_rent_evidence(
        self, property_id: str, conversation_id: str, *, action_hash: str,
        evidence: dict,
    ) -> Property | None:
        return property_store.update_public_rent_evidence(
            property_id, conversation_id, action_hash=action_hash,
            evidence=evidence,
        )

    def record_public_action_no_evidence(
        self, property_id: str, conversation_id: str, *, action_hash: str,
    ) -> Property | None:
        return property_store.record_public_action_no_evidence(
            property_id, conversation_id, action_hash=action_hash,
        )

    def update_action_feedback(
        self, property_id: str, conversation_id: str, *, action_hash: str,
        move_type: str, label: str, why: str, state_hash: str,
    ) -> Property | None:
        return property_store.update_action_feedback(
            property_id, conversation_id, action_hash=action_hash,
            move_type=move_type, label=label, why=why, state_hash=state_hash,
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
