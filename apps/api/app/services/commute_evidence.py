from dataclasses import dataclass

from app.models.profile import LivingProfile


@dataclass(frozen=True)
class CommuteEvidence:
    area: str
    commute_minutes: int
    source: str

    def prompt_context(self) -> str:
        return (
            f"Authoritative commute evidence for {self.area}: commute is "
            f"approximately {self.commute_minutes} minutes per day. Treat this "
            "as a grounded constraint when balancing independent living and "
            f"commute. Source: {self.source}."
        )


def get_commute_evidence(profile: LivingProfile) -> CommuteEvidence | None:
    location = " ".join(
        value.lower()
        for value in (profile.preferred_city, profile.work_location)
        if value
    )
    if not ("成都" in location and ("合作路" in location or "高新区" in location)):
        return None

    return CommuteEvidence(
        area="成都高新区合作路附近",
        commute_minutes=65,
        source="LiveOS Beta-05 commute evidence fixture",
    )
