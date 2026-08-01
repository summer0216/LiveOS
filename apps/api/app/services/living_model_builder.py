from app.core.logger import logger
from app.models.profile import LivingProfile
from app.runtime.living_model import (
    LivingModel,
    LivingModelProfile,
    empty_living_model,
)
from app.runtime.memory_context import DecisionMemoryContext


class LivingModelBuilder:
    def build(
        self,
        conversation_id: str,
        profile: LivingProfile,
        memory_context: DecisionMemoryContext,
    ) -> LivingModel:
        normalized_conversation_id = conversation_id.strip()

        try:
            return self._build(
                normalized_conversation_id,
                profile,
                memory_context,
            )
        except Exception:
            logger.exception("Failed to build Living Model; using empty model.")
            return empty_living_model(normalized_conversation_id)

    def _build(
        self,
        conversation_id: str,
        profile: LivingProfile,
        memory_context: DecisionMemoryContext,
    ) -> LivingModel:
        if not conversation_id:
            raise ValueError("Conversation ID must not be empty.")

        if memory_context.conversation_id != conversation_id:
            raise ValueError("Memory Context conversation mismatch.")

        return LivingModel(
            conversation_id=conversation_id,
            profile=LivingModelProfile.model_validate(profile),
            decision_memory=[
                memory.model_copy(deep=True)
                for memory in memory_context.memories
            ],
        )


living_model_builder = LivingModelBuilder()
