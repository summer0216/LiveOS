from dataclasses import dataclass

from app.models.profile import LivingProfile


@dataclass(frozen=True)
class NearbyRentEvidence:
    area: str
    independent_min_rent: int
    independent_max_rent: int
    source: str

    def supports_budget(self, budget: int) -> bool:
        return self.independent_min_rent <= budget <= self.independent_max_rent

    def prompt_context(self) -> str:
        return (
            f"Authoritative nearby rent evidence for {self.area}: independent "
            f"rent is approximately {self.independent_min_rent}-"
            f"{self.independent_max_rent} RMB/month. Treat this evidence as "
            "higher priority than model prior knowledge. If the user's budget "
            "falls within this range, treat independent living as feasible and "
            "do not recommend shared rental solely from prior knowledge. Source: "
            f"{self.source}."
        )


def get_nearby_rent_evidence(
    profile: LivingProfile,
) -> NearbyRentEvidence | None:
    location = " ".join(
        value.lower()
        for value in (profile.preferred_city, profile.work_location)
        if value
    )
    if not ("成都" in location and ("合作路" in location or "高新区" in location)):
        return None
    if profile.budget is None or profile.family_size != 1:
        return None

    return NearbyRentEvidence(
        area="成都高新区合作路附近",
        independent_min_rent=1900,
        independent_max_rent=2300,
        source="LiveOS Beta-05 nearby rent evidence fixture",
    )
