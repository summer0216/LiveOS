import hashlib
import json
from uuid import uuid4

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
from app.models.possible_life_reality_action import (
    PossibleLifeRealityAction,
    PossibleLifeRealityActionType,
)
from app.models.reality_need import RealityNeed, RealityNeedResolutionMode
from app.stores.persistent import (
    PossibleLifeMeaningfulUnknownStore,
    PossibleLifePersonalMeaningStore,
    PossibleLifeRealityActionStore,
    PossibleLifeStore,
    RealityNeedStore,
)
from app.stores.runtime import (
    possible_life_meaningful_unknown_store,
    possible_life_personal_meaning_store,
    possible_life_reality_action_store,
    possible_life_store,
    reality_need_store,
)


class PossibleLifeRealityActionService:
    def __init__(
        self,
        *,
        possible_lives: PossibleLifeStore = possible_life_store,
        unknowns: PossibleLifeMeaningfulUnknownStore = (
            possible_life_meaningful_unknown_store
        ),
        meanings: PossibleLifePersonalMeaningStore = (
            possible_life_personal_meaning_store
        ),
        needs: RealityNeedStore = reality_need_store,
        actions: PossibleLifeRealityActionStore = (
            possible_life_reality_action_store
        ),
        intelligence: AIClient = ai_client,
    ) -> None:
        self._possible_lives = possible_lives
        self._unknowns = unknowns
        self._meanings = meanings
        self._needs = needs
        self._actions = actions
        self._intelligence = intelligence

    def form(
        self, conversation_id: str, reality_need: RealityNeed,
    ) -> PossibleLifeRealityAction | None:
        admitted_need = self._needs.get(
            conversation_id, reality_need.meaningful_unknown_id,
        )
        if admitted_need != reality_need:
            return None
        possible_life = self._possible_lives.get(
            conversation_id, admitted_need.possible_life_id,
        )
        unknown = self._unknowns.get(
            conversation_id, admitted_need.possible_life_id,
        )
        meaning = self._meanings.get(
            conversation_id, admitted_need.possible_life_id,
        )
        if (
            possible_life is None
            or unknown is None
            or meaning is None
            or possible_life.id != admitted_need.possible_life_id
            or unknown.id != admitted_need.meaningful_unknown_id
            or unknown.personal_meaning_id != meaning.id
            or meaning.possible_life_id != possible_life.id
        ):
            return None
        existing = self._actions.get(conversation_id, admitted_need.id)
        if admitted_need.resolution_mode != RealityNeedResolutionMode.REAL_WORLD_CONTACT:
            if existing is not None:
                self._actions.delete(conversation_id, admitted_need.id)
            return None

        context = {
            "version": "v0.4-possible-life-reality-action",
            "possible_life_id": possible_life.id,
            "reality_need_id": admitted_need.id,
            "reality_need_state_hash": admitted_need.state_hash,
            "needed_reality": admitted_need.needed_reality,
            "unknown": unknown.question,
            "why_unknown_matters": unknown.why_it_matters,
            "personal_meaning_id": meaning.id,
            "personal_meaning": meaning.meaning,
        }
        state_hash = hashlib.sha256(json.dumps(
            context, ensure_ascii=False, sort_keys=True,
        ).encode()).hexdigest()
        if existing is not None and existing.state_hash == state_hash:
            return existing

        prompt = (
            "Choose ONE plan to obtain the Reality required by this authoritative "
            "REAL_WORLD_CONTACT Need. Do not execute the plan or claim that "
            "evidence was found. PUBLIC_EVIDENCE means obtain traceable public "
            "evidence that can reasonably answer this specific Need. "
            "USER_REALITY means the user must newly contact someone, inspect, "
            "observe, or verify in the real world. Merely asking for a fact the "
            "user already knows is not USER_REALITY. Do not invent a source, "
            "answer, recommendation, ranking, or provider. Return null if no "
            "reliable acquisition plan fits. Otherwise return a JSON object "
            "with exactly possible_life_id, reality_need_id, "
            "needed_reality_reference (the exact needed_reality), action_type "
            "(PUBLIC_EVIDENCE or USER_REALITY), action_label (concise Chinese "
            "acquisition step), and why_this_action (concise Chinese reason).\n"
            f"Context: {json.dumps(context, ensure_ascii=False, sort_keys=True)}"
        )
        try:
            proposed = json.loads(self._intelligence.generate_json(
                prompt,
                model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                max_output_tokens=320,
            ))
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return None
        if not isinstance(proposed, dict) or set(proposed) != {
            "possible_life_id", "reality_need_id", "needed_reality_reference",
            "action_type", "action_label", "why_this_action",
        }:
            return None
        label = proposed.get("action_label")
        why = proposed.get("why_this_action")
        if (
            proposed.get("possible_life_id") != possible_life.id
            or proposed.get("reality_need_id") != admitted_need.id
            or proposed.get("needed_reality_reference")
            != admitted_need.needed_reality
            or not isinstance(label, str)
            or not label.strip()
            or len(label.strip()) > 80
            or not isinstance(why, str)
            or not why.strip()
            or len(why.strip()) > 120
        ):
            return None
        try:
            action_type = PossibleLifeRealityActionType(proposed.get("action_type"))
        except (TypeError, ValueError):
            return None
        if any(term in f"{label} {why}" for term in (
            "已查到", "已证实", "已确认", "已经确认", "推荐", "最佳", "应该选择",
        )):
            return None
        return self._actions.save(
            conversation_id,
            PossibleLifeRealityAction(
                id=existing.id if existing is not None else str(uuid4()),
                possible_life_id=possible_life.id,
                reality_need_id=admitted_need.id,
                action_type=action_type,
                label=label.strip(),
                why=why.strip(),
                state_hash=state_hash,
            ),
        )


possible_life_reality_action_service = PossibleLifeRealityActionService()
