from pydantic import BaseModel, ConfigDict

from app.core.logger import logger
from app.runtime.living_model import LivingModel
from app.schemas.decision_context import DecisionContext


class AdaptiveDecisionContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    memory_count: int
    history_count: int


class AdaptiveDecision:
    """Builds a strategy layer from existing runtime context only."""

    def build(
        self,
        living_model: LivingModel,
        decision_context: DecisionContext,
    ) -> str | None:
        try:
            context = self._build_context(living_model, decision_context)
            return self._build_guidance(context)
        except Exception:
            logger.exception(
                "Adaptive Decision construction failed; "
                "continuing with Decision Intelligence.",
            )
            return None

    def _build_context(
        self,
        living_model: LivingModel,
        decision_context: DecisionContext,
    ) -> AdaptiveDecisionContext:
        return AdaptiveDecisionContext(
            memory_count=len(living_model.decision_memory),
            history_count=len(decision_context.recent_decisions),
        )

    def _build_guidance(self, context: AdaptiveDecisionContext) -> str:
        memory_guidance = (
            "Evolved Decision Memory is available. Use only supported, "
            "still-consistent long-term patterns to adjust decision strategy."
            if context.memory_count
            else (
                "No evolved Decision Memory is available. Do not claim that "
                "past learning changed this decision."
            )
        )
        history_guidance = (
            "Recent Decision History is available for evidence-backed "
            "continuity and change comparison only."
            if context.history_count
            else (
                "No Decision History is available. Do not claim that this "
                "decision differs from an earlier one."
            )
        )

        return "\n".join(
            (
                "Adaptive context priority is fixed: Current Facts > Living "
                "Model > Memory Evolution > Decision History.",
                memory_guidance,
                history_guidance,
                "Adapt only the decision strategy. Never modify current "
                "facts, Property data, Living Model data, or user input.",
                "Never create a preference or change that is absent from the "
                "supplied evidence.",
                "When current evidence shows a real change in budget, "
                "commute preference, housing quality preference, or family "
                "structure, let that change affect candidate weighting.",
                "If the current recommendation differs from past decisions, "
                "explain the evidence-backed change concisely in reasons or "
                "trade-offs. Do not force a difference when none is proven.",
                "Return user-facing conclusions only. Never reveal hidden "
                "reasoning or chain of thought.",
            ),
        )


adaptive_decision = AdaptiveDecision()
