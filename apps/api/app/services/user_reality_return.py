"""Admit a focused user's answer to the active USER_REALITY Unknown."""

import hashlib
import json
import math
from dataclasses import dataclass

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
from app.models.conversation import ConversationMessage
from app.models.possible_life import PossibleLife
from app.models.possible_life_personal_meaning import PossibleLifePersonalMeaning
from app.models.possible_life_reality_action import PossibleLifeRealityActionType
from app.models.property import GeographicStatus, Property, PropertyRentSource
from app.models.reality_need import RealityNeedResolutionMode
from app.models.work_subject import WorkSubject
from app.services.external_rent_reality_service import (
    USER_INITIATED_RENT_ACTION_LABEL,
    USER_INITIATED_RENT_ACTION_WHY,
)
from app.services.property_manager import PropertyManager, property_manager
from app.stores.persistent import (
    PossibleLifeMeaningfulUnknownStore,
    PossibleLifePersonalMeaningStore,
    PossibleLifeRealityActionStore,
    PossibleLifeStore,
    RealityNeedStore,
    WorkSubjectStore,
)
from app.stores.runtime import (
    possible_life_meaningful_unknown_store,
    possible_life_personal_meaning_store,
    possible_life_reality_action_store,
    possible_life_store,
    reality_need_store,
    work_subject_store,
)


def _amount_is_explicit(user_text: str, amount: int) -> bool:
    compact = user_text.replace(",", "")
    digits = str(amount)
    start = compact.find(digits)
    while start >= 0:
        end = start + len(digits)
        if (start == 0 or not compact[start - 1].isdigit()) and (
            end == len(compact) or not compact[end].isdigit()
        ):
            return True
        start = compact.find(digits, start + 1)
    return False


@dataclass(frozen=True)
class PossibleLifeAttentionTarget:
    possible_life: PossibleLife
    personal_meaning: PossibleLifePersonalMeaning


@dataclass(frozen=True)
class ActionRealityReturnContext:
    action_id: str
    reality_need_id: str
    possible_life_id: str
    residence_property_id: str
    claim_quote: str
    user_expression: str


@dataclass(frozen=True)
class PropertyExpressionResolution:
    property_id: str | None = None
    reality_type: str | None = None
    needs_clarification: bool = False
    layout_requirement: str | None = None
    attention_property_id: str | None = None
    rent_verification_property_id: str | None = None
    attention_subject: WorkSubject | None = None
    attention_possible_life: PossibleLifeAttentionTarget | None = None
    action_reality_return: ActionRealityReturnContext | None = None


class UserRealityReturn:
    def __init__(
        self, *, properties: PropertyManager = property_manager,
        intelligence: AIClient = ai_client,
        subjects: WorkSubjectStore = work_subject_store,
        possible_lives: PossibleLifeStore = possible_life_store,
        possible_life_meanings: PossibleLifePersonalMeaningStore = (
            possible_life_personal_meaning_store
        ),
        possible_life_unknowns: PossibleLifeMeaningfulUnknownStore = (
            possible_life_meaningful_unknown_store
        ),
        reality_needs: RealityNeedStore = reality_need_store,
        possible_life_actions: PossibleLifeRealityActionStore = (
            possible_life_reality_action_store
        ),
    ) -> None:
        self._properties = properties
        self._intelligence = intelligence
        self._subjects = subjects
        self._possible_lives = possible_lives
        self._possible_life_meanings = possible_life_meanings
        self._possible_life_unknowns = possible_life_unknowns
        self._reality_needs = reality_needs
        self._possible_life_actions = possible_life_actions

    def resolve_expression(
        self, history: list[ConversationMessage], properties: list[Property],
        user_text: str, focused_property_id: str | None = None,
        conversation_id: str | None = None,
    ) -> PropertyExpressionResolution:
        """Understand claim nature and referent before Property admission."""
        candidates = [home for home in properties if (
            home.id and home.title and home.geographic_status == GeographicStatus.GROUNDED
        )]
        prior_user_texts = [
            item.content for item in history[:-1] if item.role == "user"
        ]
        authoritative_subject = (
            self._subjects.get(conversation_id) if conversation_id else None
        )
        authoritative_possible_lives = (
            self._possible_lives.list(conversation_id) if conversation_id else []
        )
        possible_life_meanings = {
            item.possible_life_id: item
            for item in (
                self._possible_life_meanings.list(conversation_id)
                if conversation_id else []
            )
        }
        prompt = f"""
Interpret the CURRENT user expression before any Property Reality admission.
Classify its nature as PERSONAL_REQUIREMENT, PROPERTY_REALITY, REALITY_ACTION,
or OTHER.
REALITY_ACTION applies only to an explicit user request to verify or acquire
the actual RENT for the currently focused grounded residence. The request is
not a statement of Rent Reality. A factual rent statement, desired rent,
hypothetical, or unrelated question is not REALITY_ACTION.
An unqualified room count in a housing-search context may describe a desired
layout rather than an observed layout of a particular residence.
Do not turn a wish, constraint, requirement, or hypothetical into Property Reality.
PROPERTY_REALITY requires an explicit factual claim about an existing residence,
or a factual answer to its active Unknown. Resolve which residence it concerns
using the current expression, prior USER conversation, and Focus as context
evidence. Focus is not proof that every sentence describes that residence.
When the focused grounded residence has an active Unknown explicitly asking for
its actual layout, a terse direct layout answer is PROPERTY_REALITY / LAYOUT and
binds to that focused residence. Without that active answer context, the same
terse layout expression remains a PERSONAL_REQUIREMENT unless the user otherwise
states it as an actual fact about a reliably resolved residence.
Prior user messages may establish an unambiguous referent. Mere candidate count
or map visibility never establishes one. Ignore assistant claims.

Prior user messages: {json.dumps(prior_user_texts, ensure_ascii=False)}
Current message: {json.dumps(user_text, ensure_ascii=False)}
Focused residence id (context evidence only): {json.dumps(focused_property_id)}
Grounded residences: {json.dumps([{"id": p.id, "title": p.title, "active_unknown": p.meaningful_unknown if p.meaningful_unknown_state_hash else None} for p in candidates], ensure_ascii=False)}
Authoritative Work Subject: {json.dumps(self._subject_prompt_value(authoritative_subject), ensure_ascii=False)}
Authoritative Possible Lives with Personal Meaning: {json.dumps(self._possible_life_prompt_values(authoritative_possible_lives, possible_life_meanings, candidates), ensure_ascii=False)}

Return JSON only: {{"claim_nature": "PERSONAL_REQUIREMENT or PROPERTY_REALITY or REALITY_ACTION or OTHER",
"layout_requirement": "short exact current-user quote expressing their required room layout" or null,
"reality_type": "LAYOUT or RENT or TENANCY_MODE or INDEPENDENT_BATHROOM or INDEPENDENT_KITCHEN or INDOOR_SOUND_OBSERVATION" or null,
"claim_quote": "exact contiguous current-message quote" or null,
"property_id": "grounded residence id" or null,
"binding_evidence": "exact contiguous user quote naming the residence" or null,
"binding_source": "USER_EXPRESSION or FOCUS" or null,
"attention_property_id": "grounded residence id" or null,
"attention_evidence": "exact contiguous PRIOR user quote naming that residence" or null,
"attention_subject_identity": "exact authoritative Work Subject identity" or null,
"attention_subject_evidence": "exact contiguous USER quote naming that Work Subject" or null,
"attention_possible_life_id": "exact authoritative Possible Life ID" or null,
"attention_possible_life_evidence": "exact contiguous USER quote selecting that Possible Life" or null}}.
For PROPERTY_REALITY without reliable referent, return null property_id and
binding fields. For Focus binding, use FOCUS and null binding_evidence.
For REALITY_ACTION, use reality_type RENT, an exact current-message request
quote, and the same Property binding fields as PROPERTY_REALITY. Do not claim
that Rent Reality has been established.
For requirement/other, return null reality_type, property_id, binding fields.
Attention is separate from Property Reality admission. Set attention_property_id
only when the CURRENT expression continues unambiguous attention to a residence
explicitly named by the USER in a PRIOR message. A requirement by itself, a
single visible/available residence, or Focus alone does not establish attention.
If the prior USER expression names one grounded home and the CURRENT expression
continues considering living there (including adding personal housing conditions),
return that home's attention id and the exact prior USER naming quote. Its
active_unknown may be null: an Unknown is not required to establish attention.
Keep a personal condition in layout_requirement, never in Property Reality.
Never set attention for an initial named-home grounding turn. If several homes
remain plausible, return null attention fields. Quote the prior user evidence;
do not use assistant text or a Property title from the candidate list alone.
Set attention_subject_identity only when the CURRENT expression unambiguously
selects or continues attention to the authoritative Work Subject. Copy its exact
identity and cite an exact current or prior USER quote that names it. The Work
Subject data is context only: never invent a Subject, identity, relationship,
precision, or coordinates. Return null Subject attention fields when there is no
authoritative Work Subject or the current expression concerns another subject.
Set attention_possible_life_id only when the CURRENT expression unambiguously
selects or continues attention to one authoritative Possible Life that has an
associated Personal Meaning in the supplied context. Personal Meaning is
foregrounding context, not a score: do not rank, score, recommend, create, or
modify Possible Lives or Personal Meaning. Copy the exact Possible Life ID and
cite an exact current or prior USER quote selecting it. Return null Possible
Life attention fields when no single authoritative possibility is selected.
When the CURRENT expression explicitly names one supplied residence_identity
and speaks about attending to, considering, or foregrounding its possible life,
select the Possible Life containing that residence and copy its exact ID. The
user does not need to know or say the Possible Life ID.
Retain an explicit desired room layout in layout_requirement only when it is
the user's own requirement, including a terse requirement in a housing-search
context. Use an exact contiguous current-message quote, at most 60 characters.
Do not copy an actual residence layout into this field. A budget alone does not
establish a layout requirement. Return null when no layout requirement is stated.
""".strip()
        try:
            result = json.loads(self._intelligence.generate_json(
                prompt, model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                max_output_tokens=240,
            ))
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return PropertyExpressionResolution()
        if not isinstance(result, dict) or set(result) - {
            "layout_requirement", "attention_property_id", "attention_evidence",
            "attention_subject_identity", "attention_subject_evidence",
            "attention_possible_life_id", "attention_possible_life_evidence",
        } != {
            "claim_nature", "reality_type", "claim_quote", "property_id",
            "binding_evidence", "binding_source",
        }:
            return PropertyExpressionResolution()
        attention_property_id = self._grounded_attention_target(
            result.get("attention_property_id"), result.get("attention_evidence"),
            prior_user_texts, user_text, candidates,
        )
        attention_subject = self._authoritative_subject_attention_target(
            result.get("attention_subject_identity"),
            result.get("attention_subject_evidence"),
            [*prior_user_texts, user_text],
            authoritative_subject,
        )
        attention_possible_life = self._authoritative_possible_life_attention_target(
            result.get("attention_possible_life_id"),
            result.get("attention_possible_life_evidence"),
            [*prior_user_texts, user_text],
            authoritative_possible_lives,
            possible_life_meanings,
        )
        if (
            attention_possible_life is None
            and result["claim_nature"] == "OTHER"
            and result.get("attention_possible_life_id") is None
            and result.get("attention_possible_life_evidence") is None
        ):
            attention_possible_life = (
                self._explicit_possible_life_attention_target(
                    user_text,
                    authoritative_possible_lives,
                    possible_life_meanings,
                    candidates,
                )
            )
        if result["claim_nature"] == "PERSONAL_REQUIREMENT":
            requirement = result.get("layout_requirement")
            active_layout_property = self._focused_active_layout_property(
                focused_property_id, candidates,
            )
            focused_action_return = None
            if (
                conversation_id
                and focused_property_id
                and isinstance(requirement, str)
                and requirement.strip()
                and requirement in user_text
                and any(home.id == focused_property_id for home in candidates)
            ):
                focused_action_return = self._action_reality_return_context(
                    conversation_id, focused_property_id, "LAYOUT", requirement,
                    user_text, authoritative_possible_lives,
                )
            # The model has already isolated an explicit layout expression, but
            # can still mislabel a terse answer as a new requirement. An active
            # layout Unknown supplies the bounded answer context; admit() still
            # independently validates the factual Reality before any write.
            if (
                (active_layout_property is not None or focused_action_return is not None)
                and isinstance(requirement, str)
                and requirement.strip()
                and len(requirement) <= 60
                and requirement in user_text
                and result["property_id"] is None
                and result["reality_type"] is None
                and result["binding_source"] is None
                and result["binding_evidence"] is None
            ):
                return PropertyExpressionResolution(
                    property_id=focused_property_id,
                    reality_type="LAYOUT",
                    action_reality_return=focused_action_return,
                )
            if (
                isinstance(requirement, str) and requirement.strip()
                and len(requirement) <= 60 and requirement in user_text
                and result["property_id"] is None and result["reality_type"] is None
                and result["binding_source"] is None and result["binding_evidence"] is None
            ):
                return PropertyExpressionResolution(
                    layout_requirement=requirement,
                    attention_property_id=attention_property_id,
                    attention_subject=attention_subject,
                    attention_possible_life=attention_possible_life,
                )
            return PropertyExpressionResolution(
                attention_subject=attention_subject,
                attention_possible_life=attention_possible_life,
            )
        claim_nature = result["claim_nature"]
        if claim_nature not in {"PROPERTY_REALITY", "REALITY_ACTION"}:
            return PropertyExpressionResolution(
                attention_subject=attention_subject,
                attention_possible_life=attention_possible_life,
            )
        reality_type = result["reality_type"]
        if claim_nature == "REALITY_ACTION":
            if (
                reality_type != "RENT" or not focused_property_id
                or result.get("layout_requirement") is not None
            ):
                return PropertyExpressionResolution()
        elif reality_type not in {
            "LAYOUT", "RENT", "TENANCY_MODE", "INDEPENDENT_BATHROOM",
            "INDEPENDENT_KITCHEN", "INDOOR_SOUND_OBSERVATION",
        }:
            return PropertyExpressionResolution()
        quote = result["claim_quote"]
        if not isinstance(quote, str) or not quote.strip() or quote not in user_text:
            return PropertyExpressionResolution()
        property_id = result["property_id"]
        evidence = result["binding_evidence"]
        if property_id is None:
            return PropertyExpressionResolution(needs_clarification=True)
        matches = [home for home in candidates if home.id == property_id]
        if len(matches) != 1:
            return PropertyExpressionResolution(needs_clarification=True)
        if result["binding_source"] == "FOCUS":
            if property_id != focused_property_id or evidence is not None:
                return PropertyExpressionResolution(needs_clarification=True)
        elif result["binding_source"] == "USER_EXPRESSION":
            user_texts = [*prior_user_texts, user_text]
            normalize = lambda value: "".join(char for char in value.casefold() if char.isalnum())
            if (not isinstance(evidence, str)
                    or not any(evidence in text for text in user_texts)
                    or normalize(matches[0].title) not in normalize(evidence)):
                return PropertyExpressionResolution(needs_clarification=True)
        else:
            return PropertyExpressionResolution(needs_clarification=True)
        if claim_nature == "REALITY_ACTION":
            if property_id != focused_property_id:
                return PropertyExpressionResolution()
            return PropertyExpressionResolution(
                rent_verification_property_id=property_id,
            )
        return PropertyExpressionResolution(
            property_id, reality_type, attention_property_id=attention_property_id,
            attention_subject=attention_subject,
            attention_possible_life=attention_possible_life,
            action_reality_return=self._action_reality_return_context(
                conversation_id, property_id, reality_type, quote,
                user_text, authoritative_possible_lives,
            ) if conversation_id else None,
        )

    def _action_reality_return_context(
        self,
        conversation_id: str,
        property_id: str,
        reality_type: str,
        claim_quote: str,
        user_text: str,
        possible_lives: list[PossibleLife],
    ) -> ActionRealityReturnContext | None:
        # Bind only a factual layout claim already resolved to one grounded
        # residence. This does not admit the claim as Reality.
        if reality_type != "LAYOUT":
            return None
        matches: list[ActionRealityReturnContext] = []
        for possible_life in possible_lives:
            if possible_life.residence_property_id != property_id:
                continue
            unknown = self._possible_life_unknowns.get(
                conversation_id, possible_life.id,
            )
            if unknown is None or unknown.possible_life_id != possible_life.id:
                continue
            if not any(term in unknown.question for term in (
                "户型", "房型", "几室", "几厅",
            )):
                continue
            need = self._reality_needs.get(conversation_id, unknown.id)
            if (
                need is None
                or need.possible_life_id != possible_life.id
                or need.meaningful_unknown_id != unknown.id
                or need.resolution_mode != RealityNeedResolutionMode.REAL_WORLD_CONTACT
            ):
                continue
            action = self._possible_life_actions.get(conversation_id, need.id)
            if (
                action is None
                or action.action_type != PossibleLifeRealityActionType.USER_REALITY
                or action.reality_need_id != need.id
                or action.possible_life_id != possible_life.id
            ):
                continue
            matches.append(ActionRealityReturnContext(
                action_id=action.id,
                reality_need_id=need.id,
                possible_life_id=possible_life.id,
                residence_property_id=property_id,
                claim_quote=claim_quote,
                user_expression=user_text,
            ))
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _possible_life_prompt_values(
        possible_lives: list[PossibleLife],
        meanings: dict[str, PossibleLifePersonalMeaning],
        properties: list[Property],
    ) -> list[dict[str, object]]:
        residences = {home.id: home for home in properties}
        values = []
        for possible_life in possible_lives:
            meaning = meanings.get(possible_life.id)
            if meaning is None:
                continue
            residence = residences.get(possible_life.residence_property_id)
            values.append({
                "id": possible_life.id,
                "residence_property_id": possible_life.residence_property_id,
                "residence_identity": residence.title if residence else None,
                "living_time_relationship_id": (
                    possible_life.living_time_residence_property_id
                ),
                "personal_meaning": {
                    "id": meaning.id,
                    "meaning": meaning.meaning,
                    "actual_travel_minutes": meaning.actual_travel_minutes,
                    "actual_travel_mode": meaning.actual_travel_mode.value,
                    "requirement_reference": meaning.requirement_reference,
                    "maximum_commute_minutes": meaning.maximum_commute_minutes,
                    "requirement_satisfied": meaning.requirement_satisfied,
                },
            })
        return values

    @staticmethod
    def _authoritative_possible_life_attention_target(
        possible_life_id: object,
        evidence: object,
        user_texts: list[str],
        possible_lives: list[PossibleLife],
        meanings: dict[str, PossibleLifePersonalMeaning],
    ) -> PossibleLifeAttentionTarget | None:
        if (
            not isinstance(possible_life_id, str)
            or not isinstance(evidence, str)
            or not any(evidence in message for message in user_texts)
        ):
            return None
        matches = [
            possible_life for possible_life in possible_lives
            if possible_life.id == possible_life_id
        ]
        if len(matches) != 1:
            return None
        meaning = meanings.get(possible_life_id)
        if meaning is None or meaning.possible_life_id != possible_life_id:
            return None
        return PossibleLifeAttentionTarget(matches[0], meaning)

    @staticmethod
    def _explicit_possible_life_attention_target(
        user_text: str,
        possible_lives: list[PossibleLife],
        meanings: dict[str, PossibleLifePersonalMeaning],
        properties: list[Property],
    ) -> PossibleLifeAttentionTarget | None:
        normalize = lambda value: "".join(
            char for char in value.casefold() if char.isalnum()
        )
        normalized_text = normalize(user_text)
        negative_attention_markers = (
            "不关注", "不考虑", "别关注", "不要关注", "无需关注", "不想考虑",
        )
        if any(marker in normalized_text for marker in negative_attention_markers):
            return None
        attention_markers = (
            "关注", "考虑", "聚焦", "可能生活", "生活可能", "生活方案",
            "这段生活", "这个生活", "attention",
        )
        if not any(marker in normalized_text for marker in attention_markers):
            return None
        residences = {home.id: home for home in properties}
        matches = []
        for possible_life in possible_lives:
            meaning = meanings.get(possible_life.id)
            residence = residences.get(possible_life.residence_property_id)
            if (
                meaning is None
                or meaning.possible_life_id != possible_life.id
                or residence is None
                or not residence.title
                or normalize(residence.title) not in normalized_text
            ):
                continue
            matches.append(PossibleLifeAttentionTarget(possible_life, meaning))
        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _subject_prompt_value(subject: WorkSubject | None) -> dict[str, object] | None:
        if subject is None:
            return None
        return {
            "identity": subject.identity,
            "relationship": subject.relationship,
            "geographic_identity": subject.geographic_identity,
            "geographic_precision": subject.geographic_precision,
            "geographic_status": subject.geographic_status,
            "lng": subject.lng,
            "lat": subject.lat,
        }

    @staticmethod
    def _authoritative_subject_attention_target(
        identity: object, evidence: object, user_texts: list[str],
        subject: WorkSubject | None,
    ) -> WorkSubject | None:
        if (
            subject is None
            or not isinstance(identity, str)
            or not isinstance(evidence, str)
            or identity != subject.identity
            or subject.relationship != "WORK"
            or subject.geographic_status != "GROUNDED"
            or subject.geographic_precision != "PLACE"
            or not math.isfinite(subject.lng)
            or not math.isfinite(subject.lat)
        ):
            return None
        normalize = lambda value: "".join(
            char for char in value.casefold() if char.isalnum()
        )
        if normalize(subject.identity) not in normalize(evidence):
            return None
        if not any(evidence in message for message in user_texts):
            return None
        return subject

    def request_rent_verification(
        self, conversation_id: str, property_id: str, user_text: str,
    ) -> Property | None:
        home = self._properties.get_scoped(property_id, conversation_id)
        if (
            home is None or home.geographic_status != GeographicStatus.GROUNDED
            or not home.title or home.lng is None or home.lat is None
            or home.rent is not None or home.meaningful_unknown is not None
        ):
            return None
        state_hash = hashlib.sha256(json.dumps({
            "version": "user-rent-verification-v0.1",
            "property_id": property_id,
            "user_expression": user_text,
        }, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if (
            home.reality_action_type == "PUBLIC_EVIDENCE"
            and home.reality_action_state_hash == state_hash
        ):
            return home
        return self._properties.update_reality_action(
            property_id, conversation_id,
            action_type="PUBLIC_EVIDENCE",
            label=USER_INITIATED_RENT_ACTION_LABEL,
            why=USER_INITIATED_RENT_ACTION_WHY,
            state_hash=state_hash,
        )

    @staticmethod
    def _focused_active_layout_property(
        focused_property_id: str | None, candidates: list[Property],
    ) -> Property | None:
        if not focused_property_id:
            return None
        matches = [home for home in candidates if home.id == focused_property_id]
        if len(matches) != 1:
            return None
        home = matches[0]
        if not UserRealityReturn._has_active_layout_unknown(home):
            return None
        return home

    @staticmethod
    def _has_active_layout_unknown(home: Property) -> bool:
        question = home.meaningful_unknown or ""
        if not home.meaningful_unknown_state_hash or not isinstance(question, str):
            return False
        normalized = "".join(question.split())
        return any(term in normalized for term in ("户型", "房型", "几室", "几厅"))

    @staticmethod
    def _grounded_attention_target(
        property_id: object, evidence: object, prior_user_texts: list[str],
        user_text: str, candidates: list[Property],
    ) -> str | None:
        if not isinstance(property_id, str) or not isinstance(evidence, str):
            return None
        matches = [home for home in candidates if home.id == property_id]
        if len(matches) != 1 or not matches[0].title:
            return None
        normalize = lambda value: "".join(char for char in value.casefold() if char.isalnum())
        title = normalize(matches[0].title)
        if not title or title not in normalize(evidence):
            return None
        # Continuity must originate in a prior USER expression, not in the
        # current grounding turn or the existence of a lone Property row.
        anchor_indices = [
            index for index, message in enumerate(prior_user_texts)
            if evidence in message
        ]
        if not anchor_indices:
            return None
        anchor_index = max(anchor_indices)
        for message in [*prior_user_texts[anchor_index:], user_text]:
            named = {
                home.id for home in candidates
                if home.title and normalize(home.title) in normalize(message)
            }
            if named and named != {property_id}:
                return None
        return property_id

    def admit(
        self, conversation_id: str, property_id: str, user_text: str,
        *, expected_reality_type: str | None = None,
        action_reality_return: ActionRealityReturnContext | None = None,
    ) -> Property | None:
        home = self._properties.get_scoped(property_id, conversation_id)
        if home is None or home.geographic_status != GeographicStatus.GROUNDED:
            return None
        if action_reality_return is not None and (
            not isinstance(action_reality_return, ActionRealityReturnContext)
            or expected_reality_type != "LAYOUT"
            or action_reality_return.user_expression != user_text
            or not action_reality_return.claim_quote.strip()
            or action_reality_return.claim_quote not in user_text
            or action_reality_return != self._action_reality_return_context(
                conversation_id, property_id, "LAYOUT",
                action_reality_return.claim_quote,
                user_text,
                self._possible_lives.list(conversation_id),
            )
        ):
            return None

        active_unknown = bool(
            home.meaningful_unknown
            and home.meaningful_unknown_state_hash
        )

        prompt = f"""
Determine whether the CURRENT user message explicitly states supported Reality
for this one focused residence. It may answer the active Decision-Relevant
Unknown or proactively state factual rent or a concrete residential layout.
Do not use prior assistant claims
as evidence. Focus may resolve which residence "this one" refers to, but an
unrelated or ambiguous message must not become Reality.

Focused residence: {json.dumps(home.title, ensure_ascii=False)}
Active Unknown: {json.dumps(home.meaningful_unknown if active_unknown else None, ensure_ascii=False)}
Current user message: {json.dumps(user_text, ensure_ascii=False)}

Supported Reality slots in this focused Possible Life:
- LAYOUT: a factual description of this focused residence's room layout.
  Value must be the shortest exact contiguous quote from this user message
  that states the layout. Do not convert a desired, hypothetical, or
  comparative layout into a fact. Do not infer a price or suitability.
- INDEPENDENT_BATHROOM: an explicit factual yes/no answer about whether the
  rented room/residence has a bathroom for its exclusive use. Value must be
  a JSON boolean. Interpret short answers against the active Unknown only.
  Do not infer bathroom count, privacy, cleanliness, quality, suitability,
  preference or value. Ambiguous, hypothetical or desired arrangements are NONE.
- TENANCY_MODE: an explicit factual answer to the active tenancy Unknown.
  Value is ENTIRE_RENT or SHARED_RENT. Interpret a short answer in the
  active question's context; wishes, hypotheticals and ambiguity are NONE.
  This establishes tenancy arrangement only, not privacy, quality or fit.
- RENT: an explicit factual monthly rent amount for this focused residence,
  even if no Unknown or Action asked for it. Value must be a JSON integer.
  A wish, budget, target, hypothetical, quote about another residence, or
  ambiguous amount is NOT rent Reality.
- INDEPENDENT_KITCHEN: a clear user-provided yes/no fact about a usable
  independent kitchen. Value must be a JSON boolean.
- INDOOR_SOUND_OBSERVATION: a direct user observation materially informing
  the active indoor-sound Unknown. Value must be an exact, contiguous quote
  from the current user message, preserving time and conditions. It describes
  only what the user observed, not a universal noise level or measurement.

Select RENT only for a factual rent statement about the focused residence.
Select LAYOUT for a factual user statement about this focused residence even
without an active Unknown. Select the other slots only when they actually
answer the active Unknown.
Return JSON only with exactly these fields:
{{"unknown_reference": "exact active Unknown", "reality_type":
  "RENT or LAYOUT or TENANCY_MODE or INDEPENDENT_BATHROOM or INDEPENDENT_KITCHEN or INDOOR_SOUND_OBSERVATION or NONE",
  "value": "integer, exact user quote, boolean, or null"}}
For RENT, LAYOUT, or when there is no active Unknown, unknown_reference must be null.
Use reality_type=NONE and value=null if unrelated, hypothetical, ambiguous,
or not a supported Reality. Never turn a preference into observed rent.
Never guess, summarize an observation into a rating, invent dB, or use
assistant inference.
""".strip()
        try:
            result = json.loads(self._intelligence.generate_json(
                prompt,
                model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                max_output_tokens=240,
            ))
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return None
        if (
            not isinstance(result, dict)
            or set(result) != {"unknown_reference", "reality_type", "value"}
        ):
            return None
        if expected_reality_type is not None and result["reality_type"] != expected_reality_type:
            return None
        if result["reality_type"] == "RENT":
            rent = result["value"]
            if (
                result["unknown_reference"] is not None
                or type(rent) is not int
                or not 1 <= rent <= 99_999_999
                or not _amount_is_explicit(user_text, rent)
            ):
                return None
            if home.rent == rent and home.rent_source == PropertyRentSource.USER_PROVIDED:
                return home
            return self._properties.update_confirmed_rent(
                property_id, conversation_id, rent, PropertyRentSource.USER_PROVIDED,
            )
        if result["reality_type"] == "LAYOUT":
            quote = result["value"]
            layout_unknown_reference_valid = (
                result["unknown_reference"] is None
                or (
                    self._has_active_layout_unknown(home)
                    and result["unknown_reference"] == home.meaningful_unknown
                )
            )
            if (
                not layout_unknown_reference_valid
                or not isinstance(quote, str)
                or not quote.strip()
                or len(quote) > 60
                or quote not in user_text
                or (
                    action_reality_return is not None
                    and quote not in action_reality_return.claim_quote
                )
            ):
                return None
            if home.layout_expression == quote and home.layout_source == "USER_PROVIDED":
                return home
            return self._properties.admit_user_layout_reality(
                property_id, conversation_id, expression=quote,
            )
        if not active_unknown or result["unknown_reference"] != home.meaningful_unknown:
            return None
        if result["reality_type"] == "TENANCY_MODE":
            if home.tenancy_mode is not None or result["value"] not in (
                "ENTIRE_RENT", "SHARED_RENT",
            ):
                return None
            return self._properties.admit_user_tenancy_reality(
                property_id, conversation_id,
                unknown_hash=home.meaningful_unknown_state_hash,
                tenancy_mode=result["value"],
            )
        if result["reality_type"] == "INDEPENDENT_BATHROOM":
            if home.independent_bathroom is not None or type(result["value"]) is not bool:
                return None
            return self._properties.admit_user_bathroom_reality(
                property_id, conversation_id,
                unknown_hash=home.meaningful_unknown_state_hash,
                independent_bathroom=result["value"],
            )
        if result["reality_type"] == "INDEPENDENT_KITCHEN":
            if home.independent_kitchen is not None or type(result["value"]) is not bool:
                return None
            return self._properties.admit_user_kitchen_reality(
                property_id, conversation_id,
                unknown_hash=home.meaningful_unknown_state_hash,
                kitchen_present=result["value"],
            )
        if result["reality_type"] == "INDOOR_SOUND_OBSERVATION":
            quote = result["value"]
            if (
                home.indoor_sound_observation is not None
                or not isinstance(quote, str)
                or not quote.strip()
                or len(quote) > 300
                or quote not in user_text
            ):
                return None
            return self._properties.admit_user_sound_observation(
                property_id, conversation_id,
                unknown_hash=home.meaningful_unknown_state_hash,
                unknown_question=home.meaningful_unknown,
                observation=quote.strip(),
            )
        return None


user_reality_return = UserRealityReturn()
