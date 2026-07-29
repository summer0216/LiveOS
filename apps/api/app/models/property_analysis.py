from dataclasses import dataclass
from app.models.property import Property


@dataclass
class PropertyAnalysis:
    property: Property
