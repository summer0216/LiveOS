import logging

from app.models.decision_geography import DecisionGeography
from app.models.property import GeographicStatus
from app.services.geographic_resolution import (
    geographic_resolver,
    identity_explicitly_names_city,
    normalize_local_geographic_identity,
)
from app.stores.runtime import decision_geography_store

logger = logging.getLogger(__name__)


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
        identity_source: str | None,
        api_key: str | None,
        current_geographic_reality: tuple[float, float] | None = None,
    ) -> DecisionGeography | None:
        normalized_identity = (
            normalize_local_geographic_identity(identity) if identity else ""
        )
        if not intent_established or identity_source != "USER" or not identity:
            persisted = self.get(conversation_id)
            logger.info(
                "Decision geography skipped conversation_id=%s "
                "identity_source=%s geographic_context=%r "
                "normalized_identity=%r resolver_status=SKIPPED "
                "persisted_status=%s",
                conversation_id,
                identity_source,
                None,
                normalized_identity or None,
                persisted.status if persisted else None,
            )
            return persisted
        if not normalized_identity:
            return self.get(conversation_id)

        direct_result = geographic_resolver.resolve(normalized_identity, None, api_key)
        context_location = None
        if (
            identity_explicitly_names_city(normalized_identity, direct_result)
            or current_geographic_reality is None
        ):
            result = direct_result
        else:
            context_location = geographic_resolver.resolve_city_context(
                current_geographic_reality[0],
                current_geographic_reality[1],
                api_key,
            )
            result = geographic_resolver.resolve(
                normalized_identity,
                context_location,
                api_key,
            )
        if result.status != GeographicStatus.GROUNDED.value:
            direct_local_result = geographic_resolver.resolve_local_area(
                normalized_identity,
                None,
                api_key,
            )
            if identity_explicitly_names_city(
                normalized_identity,
                direct_local_result,
            ):
                result = direct_local_result
            elif current_geographic_reality is not None:
                if context_location is None:
                    context_location = geographic_resolver.resolve_city_context(
                        current_geographic_reality[0],
                        current_geographic_reality[1],
                        api_key,
                    )
                result = geographic_resolver.resolve_local_area(
                    normalized_identity,
                    context_location,
                    api_key,
                )
        logger.info(
            "Decision geography resolved conversation_id=%s "
            "identity_source=%s geographic_context=%r normalized_identity=%r "
            "resolver_status=%s resolver_identity=%r",
            conversation_id,
            identity_source,
            context_location,
            normalized_identity,
            result.status,
            getattr(result, "geographic_identity", None),
        )
        status = (
            GeographicStatus.GROUNDED.value
            if result.status == GeographicStatus.GROUNDED.value
            else GeographicStatus.UNRESOLVED.value
        )
        state = DecisionGeography(
            intent_established=True,
            intent_type=intent_type,
            identity=normalized_identity,
            identity_source="USER",
            status=status,
            lng=result.lng if status == GeographicStatus.GROUNDED.value else None,
            lat=result.lat if status == GeographicStatus.GROUNDED.value else None,
        )
        persisted = decision_geography_store.save(conversation_id, state)
        logger.info(
            "Decision geography persisted conversation_id=%s status=%s identity=%r",
            conversation_id,
            persisted.status,
            persisted.identity,
        )
        return persisted


decision_geography_service = DecisionGeographyService()
