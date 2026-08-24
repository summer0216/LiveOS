from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from app.models.decision_feedback import DecisionRelevantFeedback
from app.models.profile import LivingProfile
from app.models.profile_patch import PROFILE_FIELDS, ProfileField

type ProfileValue = str | int | bool | None


@dataclass(frozen=True)
class ProfileMutationCause:
    source: Literal["PROFILE_MUTATION"]
    field: ProfileField
    operation: Literal["SET", "CLEAR"]
    before: ProfileValue
    after: ProfileValue


@dataclass(frozen=True)
class FeedbackCause:
    source: Literal["DECISION_RELEVANT_FEEDBACK"]
    observation: str
    judgment: Literal["acceptable", "unacceptable"] | None
    observed_commute_minutes: int | None


type DecisionChangeCause = ProfileMutationCause | FeedbackCause


@dataclass(frozen=True)
class ProfileMergeResult:
    profile: LivingProfile
    changed: bool
    causes: tuple[ProfileMutationCause, ...]

    def __iter__(self) -> Iterator[LivingProfile | bool]:
        # Preserve the existing two-value merge contract for current callers.
        yield self.profile
        yield self.changed


def profile_mutation_causes(
    before: LivingProfile,
    after: LivingProfile,
    clear_fields: frozenset[ProfileField],
) -> tuple[ProfileMutationCause, ...]:
    causes: list[ProfileMutationCause] = []
    for field_name in PROFILE_FIELDS:
        previous_value = getattr(before, field_name)
        current_value = getattr(after, field_name)
        if previous_value == current_value:
            continue
        causes.append(
            ProfileMutationCause(
                source="PROFILE_MUTATION",
                field=field_name,
                operation=("CLEAR" if field_name in clear_fields else "SET"),
                before=previous_value,
                after=current_value,
            )
        )
    return tuple(causes)


def feedback_cause(
    feedback: DecisionRelevantFeedback,
) -> FeedbackCause | None:
    if not feedback.relevant or feedback.observation is None:
        return None
    return FeedbackCause(
        source="DECISION_RELEVANT_FEEDBACK",
        observation=feedback.observation,
        judgment=feedback.judgment,
        observed_commute_minutes=feedback.observed_commute_minutes,
    )
