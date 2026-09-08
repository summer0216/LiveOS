from app.models.decision_geography import DecisionGeography
from app.models.property import GeographicStatus
from app.services.geographic_resolution import geographic_resolver
from app.stores.runtime import decision_geography_store


class DecisionGeographyService:
    def get(self, conversation_id: str) -> DecisionGeography | None:
        return decision_geography_store.get(conversation_id)

    def apply(
        self,
        conversation_id: str,
        *,
        intent_established: bool,
        intent_type: str | None,
        identity: str | None,
        api_key: str | None,
    ) -> DecisionGeography | None:
        if not intent_established or not identity:
            return self.get(conversation_id)

        result = geographic_resolver.resolve(identity, None, api_key)
        status = (
            GeographicStatus.GROUNDED.value
            if result.status == GeographicStatus.GROUNDED.value
            else GeographicStatus.UNRESOLVED.value
        )
        state = DecisionGeography(
            intent_established=True,
            intent_type=intent_type,
            identity=identity,
            status=status,
            lng=result.lng if status == GeographicStatus.GROUNDED.value else None,
            lat=result.lat if status == GeographicStatus.GROUNDED.value else None,
        )
        return decision_geography_store.save(conversation_id, state)


decision_geography_service = DecisionGeographyService()
