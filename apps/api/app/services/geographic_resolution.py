from dataclasses import dataclass

import httpx

from app.models.property import GeographicPrecision


@dataclass(frozen=True)
class GeographicResolutionResult:
    status: str
    geographic_identity: str | None = None
    geographic_precision: GeographicPrecision | None = None
    lng: float | None = None
    lat: float | None = None
    ambiguous: bool = False


class GeographicResolver:
    def resolve(
        self,
        title: str,
        context_location: str | None,
        api_key: str | None,
    ) -> GeographicResolutionResult:
        if not api_key:
            return GeographicResolutionResult(status="UNRESOLVED")

        address = " ".join(part for part in (context_location, title) if part)
        try:
            response = httpx.get(
                "https://restapi.amap.com/v3/geocode/geo",
                params={"key": api_key, "address": address},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return GeographicResolutionResult(status="UNRESOLVED")
        geocodes = payload.get("geocodes") or []
        if payload.get("status") != "1" or len(geocodes) != 1:
            return GeographicResolutionResult(
                status="UNRESOLVED",
                ambiguous=len(geocodes) > 1,
            )

        geocode = geocodes[0]
        formatted_address = geocode.get("formatted_address")
        if not _matches_title(title, formatted_address, geocode.get("name")):
            return GeographicResolutionResult(status="UNRESOLVED")
        location = geocode.get("location", "").split(",")
        if len(location) != 2:
            return GeographicResolutionResult(status="UNRESOLVED")
        try:
            lng, lat = (float(value) for value in location)
        except ValueError:
            return GeographicResolutionResult(status="UNRESOLVED")

        precision = _precision_for_level(geocode.get("level"))
        if precision is None:
            return GeographicResolutionResult(status="UNRESOLVED")
        return GeographicResolutionResult(
            status="GROUNDED",
            geographic_identity=formatted_address,
            geographic_precision=precision,
            lng=lng,
            lat=lat,
        )


def _precision_for_level(level: str | None) -> GeographicPrecision | None:
    if level in {"兴趣点", "门牌号", "住宅区"}:
        return GeographicPrecision.PLACE
    if level == "道路":
        return GeographicPrecision.STREET
    if level in {"市", "区县", "乡镇", "街道"}:
        return GeographicPrecision.AREA
    return None


def _matches_title(title: str, *identities: str | None) -> bool:
    normalized_title = "".join(title.split())
    return any(
        normalized_title in "".join(identity.split())
        for identity in identities
        if identity
    )


geographic_resolver = GeographicResolver()
