from __future__ import annotations

import math
from dataclasses import dataclass

import httpx

from app.models.property import CommuteMode


@dataclass(frozen=True)
class LivingTimeResult:
    minutes: int
    mode: CommuteMode


class TransitDurationService:
    """Read the shortest truthful walking or public-transit duration from AMap."""

    transit_endpoint = "https://restapi.amap.com/v5/direction/transit/integrated"
    walking_endpoint = "https://restapi.amap.com/v5/direction/walking"

    def calculate_living_time(
        self,
        *,
        origin_lng: float,
        origin_lat: float,
        destination_lng: float,
        destination_lat: float,
        api_key: str | None,
        origin_city_code: str = "0755",
        destination_city_code: str = "0755",
    ) -> LivingTimeResult | None:
        if not api_key:
            return None
        origin = f"{origin_lng:.6f},{origin_lat:.6f}"
        destination = f"{destination_lng:.6f},{destination_lat:.6f}"
        walking = self._walking_minutes(api_key, origin, destination)
        public_transit = self._public_transit_minutes(
            api_key,
            origin,
            destination,
            origin_city_code,
            destination_city_code,
        )
        results = [
            result
            for result in (
                LivingTimeResult(walking, CommuteMode.WALKING)
                if walking is not None
                else None,
                LivingTimeResult(public_transit, CommuteMode.PUBLIC_TRANSIT)
                if public_transit is not None
                else None,
            )
            if result is not None
        ]
        return (
            min(results, key=lambda result: (result.minutes, result.mode.value))
            if results
            else None
        )

    def calculate_minutes(self, **kwargs) -> int | None:
        """Backward-compatible minute projection for existing callers."""
        result = self.calculate_living_time(**kwargs)
        return result.minutes if result is not None else None

    def _walking_minutes(
        self,
        api_key: str,
        origin: str,
        destination: str,
    ) -> int | None:
        payload = self._request(
            self.walking_endpoint,
            {
                "key": api_key,
                "origin": origin,
                "destination": destination,
                "show_fields": "cost",
            },
        )
        return _shortest_duration(payload, "paths")

    def _public_transit_minutes(
        self,
        api_key: str,
        origin: str,
        destination: str,
        origin_city_code: str,
        destination_city_code: str,
    ) -> int | None:
        payload = self._request(
            self.transit_endpoint,
            {
                "key": api_key,
                "origin": origin,
                "destination": destination,
                "city1": origin_city_code,
                "city2": destination_city_code,
                "strategy": "0",
                "AlternativeRoute": "5",
                "show_fields": "cost",
            },
        )
        return _shortest_duration(payload, "transits")

    @staticmethod
    def _request(endpoint: str, params: dict[str, str]) -> dict | None:
        try:
            response = httpx.get(endpoint, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            return None
        return payload if payload.get("status") == "1" else None


def _shortest_duration(payload: dict | None, collection: str) -> int | None:
    routes = ((payload or {}).get("route") or {}).get(collection) or []
    if not isinstance(routes, list):
        return None
    durations: list[int] = []
    for route in routes:
        if not isinstance(route, dict):
            continue
        try:
            seconds = float(
                (route.get("cost") or {}).get("duration", route.get("duration"))
            )
        except (TypeError, ValueError):
            continue
        if math.isfinite(seconds) and seconds > 0:
            durations.append(max(1, math.ceil(seconds / 60)))
    return min(durations) if durations else None


transit_duration_service = TransitDurationService()
