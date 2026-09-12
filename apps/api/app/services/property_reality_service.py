from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.models.property import Property, PropertyRentSource
from app.services.property_manager import PropertyManager, property_manager

RentRealityStatus = Literal[
    "UPDATED",
    "IDEMPOTENT",
    "NO_EXPLICIT_RENT",
    "UNMATCHED",
    "AMBIGUOUS",
]

_RENT_PATTERNS = (
    re.compile(
        r"(?:租金|房租|月租)\s*(?:是|为|要|大约|约)?\s*[¥￥]?\s*(\d{2,8})(?:\s*元)?"
    ),
    re.compile(
        r"(?:一个月|每月)\s*(?:是|为|要|大约|约)?\s*[¥￥]?\s*(\d{2,8})(?:\s*元)?"
    ),
)
_IDENTITY_NOISE = re.compile(r"[\s，,。.!！?？、·—_\-]+")


def _normalize_identity(value: str) -> str:
    return _IDENTITY_NOISE.sub("", value).casefold()


@dataclass(frozen=True)
class RentRealityResult:
    status: RentRealityStatus
    property: Property | None = None
    rent: int | None = None


class PropertyRealityService:
    def __init__(self, properties: PropertyManager = property_manager) -> None:
        self._properties = properties

    def apply_explicit_rent(
        self,
        conversation_id: str,
        user_text: str,
    ) -> RentRealityResult:
        rent = self._extract_rent(user_text)
        if rent is None:
            return RentRealityResult(status="NO_EXPLICIT_RENT")

        normalized_text = _normalize_identity(user_text)
        matches = [
            property_
            for property_ in self._properties.list(conversation_id)
            if property_.conversation_id == conversation_id
            and property_.id is not None
            and property_.title
            and _normalize_identity(property_.title) in normalized_text
        ]
        if not matches:
            return RentRealityResult(status="UNMATCHED", rent=rent)
        if len(matches) != 1:
            return RentRealityResult(status="AMBIGUOUS", rent=rent)

        property_ = matches[0]
        if (
            property_.rent == rent
            and property_.rent_source == PropertyRentSource.USER_CONFIRMED_REALITY
        ):
            return RentRealityResult(
                status="IDEMPOTENT",
                property=property_,
                rent=rent,
            )

        updated = self._properties.update_confirmed_rent(
            property_.id or "",
            conversation_id,
            rent,
        )
        if updated is None:
            return RentRealityResult(status="UNMATCHED", rent=rent)
        return RentRealityResult(status="UPDATED", property=updated, rent=rent)

    @staticmethod
    def _extract_rent(user_text: str) -> int | None:
        for pattern in _RENT_PATTERNS:
            match = pattern.search(user_text)
            if match is not None:
                value = int(match.group(1))
                return value if value > 0 else None
        return None


property_reality_service = PropertyRealityService()
