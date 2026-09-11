import re
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


_LOCAL_RELATION_SUFFIXES = ("附近", "周边", "那边", "一带")
_MUNICIPALITIES = ("北京", "上海", "天津", "重庆")


def normalize_local_geographic_identity(identity: str) -> str:
    """Remove trailing relation words that are not part of place identity."""
    normalized = identity.strip().rstrip("，。！？,.!? ")
    while normalized:
        without_suffix = next(
            (
                normalized[: -len(suffix)].rstrip()
                for suffix in _LOCAL_RELATION_SUFFIXES
                if normalized.endswith(suffix)
            ),
            normalized,
        )
        if without_suffix == normalized:
            break
        normalized = without_suffix
    return normalized


class GeographicResolver:
    def resolve_city_context(
        self,
        lng: float,
        lat: float,
        api_key: str | None,
    ) -> str | None:
        if not api_key:
            return None
        try:
            response = httpx.get(
                "https://restapi.amap.com/v3/geocode/regeo",
                params={"key": api_key, "location": f"{lng},{lat}"},
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return None
        if payload.get("status") != "1":
            return None
        component = (payload.get("regeocode") or {}).get("addressComponent") or {}
        city = component.get("city")
        if isinstance(city, str) and city.strip():
            return city.strip()
        return None

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
        if context_location is None and len(geocodes) > 1:
            identity_matches = [
                geocode
                for geocode in geocodes
                if isinstance(geocode, dict)
                and _geocode_matches_identity(title, geocode)
            ]
            geocodes = identity_matches
        if payload.get("status") != "1" or len(geocodes) != 1:
            return GeographicResolutionResult(
                status="UNRESOLVED",
                ambiguous=len(geocodes) > 1,
            )

        geocode = geocodes[0]
        formatted_address = geocode.get("formatted_address")
        if not _geocode_matches_identity(title, geocode):
            return GeographicResolutionResult(status="UNRESOLVED")
        location = geocode.get("location", "").split(",")
        if len(location) != 2:
            return GeographicResolutionResult(status="UNRESOLVED")
        try:
            lng, lat = (float(value) for value in location)
        except ValueError:
            return GeographicResolutionResult(status="UNRESOLVED")

        precision = _precision_for_level(
            geocode.get("level"),
            title=title,
            formatted_address=formatted_address,
        )
        if precision is None:
            return GeographicResolutionResult(status="UNRESOLVED")
        return GeographicResolutionResult(
            status="GROUNDED",
            geographic_identity=formatted_address,
            geographic_precision=precision,
            lng=lng,
            lat=lat,
        )

    def resolve_local_area(
        self,
        title: str,
        context_location: str | None,
        api_key: str | None,
    ) -> GeographicResolutionResult:
        """Resolve a natural-language local area only from one canonical POI."""
        if not api_key:
            return GeographicResolutionResult(status="UNRESOLVED")
        try:
            response = httpx.get(
                "https://restapi.amap.com/v3/place/text",
                params={
                    "key": api_key,
                    "keywords": title,
                    **({"city": context_location, "citylimit": "true"} if context_location else {}),
                    "offset": 20,
                    "page": 1,
                },
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return GeographicResolutionResult(status="UNRESOLVED")
        if payload.get("status") != "1":
            return GeographicResolutionResult(status="UNRESOLVED")

        candidates = [
            candidate
            for candidate in payload.get("pois") or []
            if isinstance(candidate, dict)
            and _poi_is_within_context(candidate, context_location)
            and _poi_match_score(title, candidate) is not None
        ]
        if not candidates:
            return GeographicResolutionResult(status="UNRESOLVED")

        ranked = sorted(
            ((_poi_match_score(title, candidate), candidate) for candidate in candidates),
            key=lambda item: item[0],
            reverse=True,
        )
        best_score, best = ranked[0]
        if len(ranked) > 1 and ranked[1][0] == best_score:
            return GeographicResolutionResult(status="UNRESOLVED", ambiguous=True)

        location = str(best.get("location") or "").split(",")
        if len(location) != 2:
            return GeographicResolutionResult(status="UNRESOLVED")
        try:
            lng, lat = (float(value) for value in location)
        except ValueError:
            return GeographicResolutionResult(status="UNRESOLVED")
        name = best.get("name")
        if not isinstance(name, str) or not name.strip():
            return GeographicResolutionResult(status="UNRESOLVED")
        city = best.get("cityname")
        geographic_identity = "".join(
            part for part in (city if isinstance(city, str) else None, name.strip()) if part
        )
        return GeographicResolutionResult(
            status="GROUNDED",
            geographic_identity=geographic_identity,
            geographic_precision=_poi_precision(str(best.get("type") or "")),
            lng=lng,
            lat=lat,
        )


def _precision_for_level(
    level: str | None,
    *,
    title: str,
    formatted_address: str | None,
) -> GeographicPrecision | None:
    if level in {"兴趣点", "门牌号", "门址", "住宅区"}:
        return GeographicPrecision.PLACE
    if level == "道路":
        return GeographicPrecision.STREET
    if level in {"市", "区县", "乡镇", "街道"}:
        return GeographicPrecision.AREA
    if level == "未知" and formatted_address and _matches_title(
        title, formatted_address
    ):
        return GeographicPrecision.AREA
    if level == "省" and formatted_address:
        normalized_title = _normalize_administrative_text(title)
        normalized_address = _normalize_administrative_text(formatted_address)
        if normalized_title in _MUNICIPALITIES and normalized_address == normalized_title:
            return GeographicPrecision.AREA
    return None


def _matches_title(title: str, *identities: str | None) -> bool:
    normalized_title = "".join(title.split())
    return any(
        normalized_title in "".join(identity.split())
        or _normalize_administrative_text(normalized_title)
        in _normalize_administrative_text(identity)
        for identity in identities
        if identity
    )


def _geocode_matches_identity(title: str, geocode: dict) -> bool:
    formatted_address = geocode.get("formatted_address")
    name = geocode.get("name")
    if not _matches_title(title, formatted_address, name):
        return False

    candidate_fields = {
        "省": geocode.get("province"),
        "市": geocode.get("city"),
        "区": geocode.get("district"),
        "县": geocode.get("district"),
    }
    for token in re.findall(r"([^省市区县]+[省市区县])", title):
        field = candidate_fields[token[-1]]
        if isinstance(field, str) and field and token not in field:
            return False

    street_number = re.search(r"([0-9一二三四五六七八九十百]+号)", title)
    return street_number is None or any(
        street_number.group(1) in identity
        for identity in (formatted_address, name)
        if isinstance(identity, str)
    )


def _normalize_administrative_text(value: str) -> str:
    return re.sub(r"[省市区县]", "", "".join(value.split()))


def _poi_is_within_context(candidate: dict, context_location: str | None) -> bool:
    if context_location is None:
        return True
    city = candidate.get("cityname")
    return isinstance(city, str) and city.replace("市", "") == context_location.replace("市", "")


def _poi_match_score(title: str, candidate: dict) -> int | None:
    name = candidate.get("name")
    category = str(candidate.get("type") or "")
    if not isinstance(name, str) or not _is_local_geography_category(category):
        return None
    normalized_title = _normalize_location_text(title)
    normalized_name = _normalize_location_text(name)
    city = candidate.get("cityname")
    normalized_identity = _normalize_location_text(
        f"{city or ''}{name}",
    )
    if normalized_title in normalized_name or normalized_title in normalized_identity:
        match_score = 100
    elif _matches_directional_local_alias(normalized_title, normalized_name):
        match_score = 50
    else:
        return None
    exact_name_score = 30 if normalized_title == normalized_name else 0
    category_score = (
        70
        if "区县级地名" in category
        else 40
        if "交通地名;道路名" in category
        else 20
    )
    canonical_score = 20 if _looks_like_canonical_area(name) else 0
    return match_score + exact_name_score + category_score + canonical_score


def _is_local_geography_category(category: str) -> bool:
    return category.startswith("地名地址信息") or "产业园区" in category


def _poi_precision(category: str) -> GeographicPrecision:
    return GeographicPrecision.STREET if "交通地名;道路名" in category else GeographicPrecision.AREA


def _looks_like_canonical_area(name: str) -> bool:
    normalized = re.sub(r"[\s()（）·-]", "", name)
    return normalized.endswith(("区", "路", "街", "园", "城", "开发区"))


def _normalize_location_text(value: str) -> str:
    return re.sub(r"[\s()（）·-]", "", value).replace("市", "").replace("区", "")


def _matches_directional_local_alias(identity: str, candidate_name: str) -> bool:
    if len(identity) < 3 or identity[-1] not in "东西南北":
        return False
    stem = identity[:-1]
    direction = identity[-1]
    return stem in candidate_name and candidate_name.endswith(direction)


geographic_resolver = GeographicResolver()


def identity_explicitly_names_city(
    identity: str,
    direct_result: GeographicResolutionResult,
) -> bool:
    geographic_identity = getattr(direct_result, "geographic_identity", None)
    if not geographic_identity:
        return False
    city_match = re.search(r"([^省]+?市)", geographic_identity)
    if city_match is None:
        return False
    city = city_match.group(1).removesuffix("市")
    return bool(city) and city in identity.replace("市", "")
