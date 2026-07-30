from dataclasses import dataclass


@dataclass
class Property:
    id: str | None = None
    conversation_id: str | None = None
    title: str | None = None
    district: str | None = None
    rent: int | None = None
    area: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    commute_minutes: int | None = None
    pet_friendly: bool | None = None
