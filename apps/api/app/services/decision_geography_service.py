import logging
import re
from concurrent.futures import ThreadPoolExecutor

from app.models.decision_geography import DecisionGeography
from app.models.property import GeographicStatus
from app.services.geographic_resolution import (
    GeographicResolutionResult,
    geographic_resolver,
    identity_explicitly_names_city,
    normalize_local_geographic_identity,
)
from app.stores.runtime import decision_geography_store

logger = logging.getLogger(__name__)


class DecisionGeographyService:
    def __init__(self) -> None:
        self._current_city_contexts: dict[tuple[float, float, object], str] = {}

    def get(self, conversation_id: str) -> DecisionGeography | None:
        return decision_geography_store.get(conversation_id)

    def _current_city_context(
        self,
        current_geographic_reality: tuple[float, float],
        api_key: str | None,
    ) -> str | None:
        resolver_method = geographic_resolver.resolve_city_context
        resolver_function = getattr(resolver_method, "__func__", resolver_method)
        cache_key = (*current_geographic_reality, resolver_function)
        cached = self._current_city_contexts.get(cache_key)
        if cached is not None:
            return cached
        context = geographic_resolver.resolve_city_context(
            current_geographic_reality[0],
            current_geographic_reality[1],
            api_key,
        )
        if context is not None:
            self._current_city_contexts[cache_key] = context
        return context

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
            direct_result.status == GeographicStatus.GROUNDED.value
            or identity_explicitly_names_city(normalized_identity, direct_result)
        ):
            result = direct_result
        elif current_geographic_reality is None:
            result = direct_result
            if result.status != GeographicStatus.GROUNDED.value:
                direct_local_result = geographic_resolver.resolve_local_area(
                    normalized_identity, None, api_key
                )
                if identity_explicitly_names_city(
                    normalized_identity, direct_local_result
                ):
                    result = direct_local_result
        else:
            context_location = self._current_city_context(
                current_geographic_reality, api_key
            )
            if context_location is None:
                result = GeographicResolutionResult(status="UNRESOLVED")
            else:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    contextual_future = executor.submit(
                        geographic_resolver.resolve,
                        normalized_identity,
                        context_location,
                        api_key,
                    )
                    local_future = executor.submit(
                        geographic_resolver.resolve_local_area,
                        normalized_identity,
                        context_location,
                        api_key,
                    )
                    contextual_result = contextual_future.result()
                    local_result = local_future.result()
                result = _select_contextual_result(
                    normalized_identity,
                    context_location,
                    contextual_result,
                    local_result,
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

def _city_name(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"([^省]+?市)", value)
    return match.group(1) if match else None


def _select_contextual_result(
    identity: str,
    context: str,
    contextual: GeographicResolutionResult,
    local: GeographicResolutionResult,
) -> GeographicResolutionResult:
    if local.ambiguous:
        return GeographicResolutionResult(status="UNRESOLVED", ambiguous=True)

    contextual_grounded = contextual.status == GeographicStatus.GROUNDED.value
    local_grounded = local.status == GeographicStatus.GROUNDED.value
    if contextual_grounded:
        contextual_city = _city_name(contextual.geographic_identity)
        context_city = context.removesuffix("市")
        if contextual_city and contextual_city.removesuffix("市") != context_city:
            if contextual_city.removesuffix("市") in identity.replace("市", ""):
                return contextual
            contextual_grounded = False

    if contextual_grounded and local_grounded:
        contextual_city = _city_name(contextual.geographic_identity)
        local_city = _city_name(local.geographic_identity)
        if contextual_city and local_city and contextual_city != local_city:
            return GeographicResolutionResult(status="UNRESOLVED", ambiguous=True)
        return contextual
    if contextual_grounded:
        return contextual
    if local_grounded:
        return local
    return GeographicResolutionResult(status="UNRESOLVED")


decision_geography_service = DecisionGeographyService()
