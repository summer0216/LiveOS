from __future__ import annotations

import math

import httpx


class TransitDurationService:
    """Read a truthful public-transit duration from AMap."""

    endpoint = "https://restapi.amap.com/v5/direction/transit/integrated"

    def calculate_minutes(
        self,
        *,
        origin_lng: float,
        origin_lat: float,
        destination_lng: float,
        destination_lat: float,
        api_key: str | None,
        origin_city_code: str = "0755",
        destination_city_code: str = "0755",
    ) -> int | None:
        if not api_key:
            return None

        params = {
            "key": api_key,
            "origin": f"{origin_lng:.6f},{origin_lat:.6f}",
            "destination": f"{destination_lng:.6f},{destination_lat:.6f}",
            "city1": origin_city_code,
            "city2": destination_city_code,
            "strategy": "0",
            "AlternativeRoute": "5",
            "show_fields": "cost",
        }
        try:
            response = httpx.get(self.endpoint, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError, TypeError):
            return None

        if payload.get("status") != "1":
            return None
        transits = (payload.get("route") or {}).get("transits") or []
        if not isinstance(transits, list):
            return None
        for transit in transits:
            if not _contains_metro(transit):
                continue
            try:
                transit_data = transit or {}
                cost = transit_data.get("cost") or {}
                seconds = float(cost.get("duration", transit_data.get("duration")))
            except (TypeError, ValueError):
                continue
            if math.isfinite(seconds) and seconds > 0:
                return max(1, math.ceil(seconds / 60))
        return None


def _contains_metro(transit: object) -> bool:
    if not isinstance(transit, dict):
        return False
    for segment in transit.get("segments") or []:
        if not isinstance(segment, dict):
            continue
        for line in (segment.get("bus") or {}).get("buslines") or []:
            if not isinstance(line, dict):
                continue
            line_type = str(line.get("type") or "").casefold()
            line_name = str(line.get("name") or "").casefold()
            if (
                "地铁" in line_type
                or "地铁" in line_name
                or "metro" in line_type
                or "metro" in line_name
                or "subway" in line_type
                or "subway" in line_name
            ):
                return True
    return False


transit_duration_service = TransitDurationService()
