from dataclasses import dataclass


@dataclass(frozen=True)
class PossibleLife:
    id: str
    work_subject_owner_id: str
    residence_property_id: str
    living_time_residence_property_id: str
    personal_meaning_reference: str
