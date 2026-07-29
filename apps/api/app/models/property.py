from dataclasses import dataclass


@dataclass
class Property:
    title: str | None = None
    district: str | None = None
    rent: int | None = None
    area: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    commute_minutes: int | None = None
    pet_friendly: bool | None = None
