from app.core.logger import logger


FALLBACK_DECISION_REASONING = """
Evaluate the current candidates against the supplied current facts and Living
Model. Return only concise, user-facing conclusions supported by the input.
Use reasons for supported benefits and trade-offs for supported compromises.
Do not reveal chain of thought or invent missing facts.
""".strip()


class DecisionIntelligence:
    """Builds stateless reasoning guidance for the existing Decision prompt."""

    def build(self, property_count: int) -> str:
        try:
            return self._build(property_count)
        except Exception:
            logger.exception(
                "Failed to build Decision Intelligence guidance; "
                "using fallback guidance.",
            )
            return FALLBACK_DECISION_REASONING

    def _build(self, property_count: int) -> str:
        candidate_guidance = (
            "There is one candidate. Evaluate its fit, advantages, risks, and "
            "information limitations without claiming a comparison."
            if property_count == 1
            else (
                "Compare the current candidates using only their supplied "
                "fields. Explain why the selected candidate represents the "
                "best supported balance."
            )
        )

        return "\n".join(
            (
                candidate_guidance,
                "Reason internally from the supplied evidence, then return "
                "only concise user-facing conclusions, never hidden chain "
                "of thought.",
                "Identify decision-relevant advantages supported by current "
                "property facts and express them in reasons.",
                "Identify risks, missing information, and conflicts that "
                "materially affect the choice.",
                "Express a trade-off only when the selected property gains a "
                "supported benefit while accepting a supported cost, risk, "
                "or limitation. If none is supported, return no trade-offs.",
                "Resolve conflicts using this fixed priority: Current Facts "
                "> Living Model > Decision History.",
                "History may provide continuity but cannot create facts, "
                "scores, rankings, advantages, risks, or trade-offs.",
            ),
        )


decision_intelligence = DecisionIntelligence()
