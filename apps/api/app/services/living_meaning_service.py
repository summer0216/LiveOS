from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
from app.models.profile import LivingProfile
from app.models.property import GeographicStatus, Property
from app.services.profile_manager import ProfileManager, profile_manager
from app.services.property_manager import PropertyManager, property_manager


@dataclass(frozen=True)
class LivingMeaningResult:
    status: str
    property: Property | None = None


class LivingMeaningService:
    meaning_version = "v0.3"
    judgment_version = "v0.4"
    unknown_version = "v0.5.1-r4"
    action_version = "v0.6"

    def __init__(
        self,
        *,
        properties: PropertyManager = property_manager,
        profiles: ProfileManager = profile_manager,
        intelligence: AIClient = ai_client,
    ) -> None:
        self._properties = properties
        self._profiles = profiles
        self._intelligence = intelligence

    def form(self, conversation_id: str, property_id: str) -> LivingMeaningResult:
        home = self._properties.get_scoped(property_id, conversation_id)
        profile = self._profiles.get(conversation_id)
        if not self._has_required_reality(home, profile):
            return LivingMeaningResult("INSUFFICIENT_REALITY", home)
        assert home is not None and profile is not None
        basis = self._basis(home, profile)
        fingerprint = hashlib.sha256(
            json.dumps(
                {"version": self.meaning_version, "reality": basis},
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        meaning_updated = False
        if not (
            home.living_meaning
            and home.living_meaning_reality_hash == fingerprint
        ):
            meaning = self._generate_meaning(basis)
            if meaning is None:
                return LivingMeaningResult("INVALID_MEANING", home)
            updated = self._properties.update_living_meaning(
                property_id,
                conversation_id,
                meaning=meaning,
                reality_hash=fingerprint,
            )
            if updated is None:
                return LivingMeaningResult("NOT_FOUND")
            home = updated
            meaning_updated = True

        assert home.living_meaning is not None
        judgment_hash = hashlib.sha256(
            json.dumps(
                {
                    "version": self.judgment_version,
                    "reality_hash": fingerprint,
                    "personal_meaning": home.living_meaning,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        judgment_updated = False
        if (
            home.current_judgment
            and home.current_judgment_state_hash == judgment_hash
        ):
            judgment = home.current_judgment
        else:
            judgment = self._generate_judgment(basis, home.living_meaning)
            if judgment is None:
                return LivingMeaningResult("INVALID_JUDGMENT", home)
            updated = self._properties.update_current_judgment(
                property_id,
                conversation_id,
                judgment=judgment,
                state_hash=judgment_hash,
            )
            if updated is None:
                return LivingMeaningResult("NOT_FOUND")
            home = updated
            judgment_updated = True

        unknown_hash = hashlib.sha256(
            json.dumps(
                {
                    "version": self.unknown_version,
                    "reality_hash": fingerprint,
                    "personal_meaning": home.living_meaning,
                    "current_judgment": judgment,
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        unknown_updated = False
        if (
            home.meaningful_unknown
            and home.meaningful_unknown_why
            and home.meaningful_unknown_state_hash == unknown_hash
        ):
            unknown = (home.meaningful_unknown, home.meaningful_unknown_why)
        else:
            unknown = self._generate_meaningful_unknown(
                basis,
                home.living_meaning,
                judgment,
            )
            if unknown is None:
                return LivingMeaningResult("INVALID_UNKNOWN", home)
            updated = self._properties.update_meaningful_unknown(
                property_id,
                conversation_id,
                question=unknown[0],
                why=unknown[1],
                state_hash=unknown_hash,
            )
            if updated is None:
                return LivingMeaningResult("NOT_FOUND")
            home = updated
            unknown_updated = True

        action_hash = hashlib.sha256(
            json.dumps(
                {
                    "version": self.action_version,
                    "unknown_hash": unknown_hash,
                    "question": unknown[0],
                    "why": unknown[1],
                },
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if (
            home.reality_action_type
            and home.reality_action_label
            and home.reality_action_why
            and home.reality_action_state_hash == action_hash
        ):
            return LivingMeaningResult(
                "UPDATED" if meaning_updated or judgment_updated or unknown_updated
                else "EXISTING",
                home,
            )
        action = self._generate_reality_action(
            basis, home.living_meaning, judgment, unknown
        )
        if action is None:
            return LivingMeaningResult("INVALID_ACTION", home)
        updated = self._properties.update_reality_action(
            property_id,
            conversation_id,
            action_type=action[0],
            label=action[1],
            why=action[2],
            state_hash=action_hash,
        )
        return LivingMeaningResult("UPDATED" if updated else "NOT_FOUND", updated)

    def _generate_reality_action(
        self,
        basis: dict[str, str],
        personal_meaning: str,
        current_judgment: str,
        unknown: tuple[str, str],
    ) -> tuple[str, str, str] | None:
        prompt = f"""
Choose ONE reliable next action to learn the Reality needed by this unresolved
Decision-Relevant Unknown. This is a plan only: do not execute, answer, or
claim the Reality was observed. Choose the acquisition mode based on the
nature of this Unknown, not a keyword rule.

PUBLIC_EVIDENCE means traceable public evidence can reasonably answer it.
USER_REALITY means public evidence is insufficient and the user's direct
knowledge or observation is needed. Do not invent a source or evidence.

Return JSON only, with exactly these fields:
{{
  "action_type": "PUBLIC_EVIDENCE or USER_REALITY",
  "action_label": "one concise Chinese acquisition action",
  "why_this_action": "one concise Chinese reason this mode is reliable",
  "unknown_reference": "exact supplied Unknown question"
}}

Grounded Reality:
{json.dumps(basis, ensure_ascii=False, sort_keys=True)}
Personal Meaning: {personal_meaning}
Current Judgment: {current_judgment}
Unknown: {unknown[0]}
Why Unknown matters: {unknown[1]}

Describe only how to obtain the missing evidence. Do not include a guessed
answer, recommendation, ranking, score, fabricated source, or completed-action
claim. Keep each Chinese text under 50 characters.
""".strip()
        try:
            interpretation = json.loads(
                self._intelligence.generate_json(
                    prompt,
                    model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                    max_output_tokens=320,
                )
            )
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return None
        if not isinstance(interpretation, dict) or set(interpretation) != {
            "action_type", "action_label", "why_this_action", "unknown_reference"
        }:
            return None
        action_type = interpretation.get("action_type")
        label = interpretation.get("action_label")
        why = interpretation.get("why_this_action")
        if (
            action_type not in {"PUBLIC_EVIDENCE", "USER_REALITY"}
            or interpretation.get("unknown_reference") != unknown[0]
            or not isinstance(label, str)
            or not label.strip()
            or len(label.strip()) > 50
            or not isinstance(why, str)
            or not why.strip()
            or len(why.strip()) > 50
        ):
            return None
        combined = f"{label} {why}"
        if any(term in combined for term in (
            "已经确认", "已确认", "已查到", "已证实", "已观察到", "推荐", "最适合",
            "最佳", "应该选择", "值得租", "不值得租"
        )):
            return None
        allowed_numbers = {
            number for value in basis.values() for number in re.findall(r"\d+", value)
        }
        if any(number not in allowed_numbers for number in re.findall(r"\d+", combined)):
            return None
        return action_type, label.strip(), why.strip()

    def _generate_meaning(self, basis: dict[str, str]) -> str | None:
        prompt = f"""
Interpret what one grounded Possible Life means for this user's daily life.
Use only the supplied Reality. Synthesize implications and trade-offs instead
of restating names, minutes, rent, and budget as a factual sentence.
Return JSON only:
{{
  "meaning": "one concise Chinese personal meaning",
  "grounding": [{{"fact": "FACT_NAME", "value": "exact supplied value"}}]
}}

Grounded Reality:
{json.dumps(basis, ensure_ascii=False, sort_keys=True)}

Allowed FACT_NAME values are exactly the keys in Grounded Reality.
Every grounding value must exactly equal its supplied value.
Ground the interpretation in at least two relevant facts, but do not
mechanically mention every fact. Qualitative meaning directly supported by the
facts is allowed: short walking relationships may mean easy daily access, and
rent above an explicit budget may mean cost pressure. Express the combined
life consequence or trade-off, not a recommendation and not a Reality summary.
Do not invent places, times, prices, distances, amenities, preferences,
recommendations, rankings, or scores. Keep meaning under 80 Chinese characters.
Refer to grocery only as "日常采购"; do not infer or name a grocery category.
""".strip()
        try:
            interpretation = json.loads(
                self._intelligence.generate_json(
                    prompt,
                    model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                    max_output_tokens=512,
                )
            )
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return None
        return self._validate_interpretation(
            interpretation,
            basis,
            text_field="meaning",
        )

    def _generate_judgment(
        self,
        basis: dict[str, str],
        personal_meaning: str,
    ) -> str | None:
        prompt = f"""
Form one provisional Current Judgment for a grounded Possible Life.
Describe what kind of life choice its current trade-off represents. Do not
recommend, rank, score, approve, reject, or make the user's decision.

Return JSON only:
{{
  "judgment": "one concise Chinese current judgment",
  "meaning_reference": "exact supplied Personal Meaning",
  "grounding": [{{"fact": "FACT_NAME", "value": "exact supplied value"}}]
}}

Grounded Reality:
{json.dumps(basis, ensure_ascii=False, sort_keys=True)}

Personal Meaning:
{personal_meaning}

Use only this Reality and Personal Meaning. Synthesize the supported trade-off
without mechanically repeating every fact. Every grounding value and the
meaning_reference must match the supplied values exactly. Do not invent user
preferences, priorities, neighborhood quality, safety, housing quality,
emotions, future prices, amenities, or new Reality. Keep judgment under 70
Chinese characters. Never use recommendation language such as 推荐、最适合、
最佳、应该选择、值得租、不值得租.
""".strip()
        try:
            interpretation = json.loads(
                self._intelligence.generate_json(
                    prompt,
                    model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                    max_output_tokens=512,
                )
            )
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return None
        if (
            not isinstance(interpretation, dict)
            or interpretation.get("meaning_reference") != personal_meaning
        ):
            return None
        judgment = self._validate_interpretation(
            interpretation,
            basis,
            text_field="judgment",
            max_length=70,
        )
        if judgment is None or any(
            term in judgment
            for term in (
                "推荐",
                "最适合",
                "最佳",
                "应该选择",
                "值得租",
                "不值得租",
            )
        ):
            return None
        return judgment

    def _generate_meaningful_unknown(
        self,
        basis: dict[str, str],
        personal_meaning: str,
        current_judgment: str,
    ) -> tuple[str, str] | None:
        prompt = f"""
Identify the ONE unknown Reality with the highest direct ability to materially
change how this grounded Possible Life is currently understood or judged.
Missing data alone does not deserve attention. Before selecting it, internally
test: (1) it is genuinely unknown, (2) different plausible real answers could
change the Current Judgment in meaningfully different ways, and (3) that impact
follows directly from supplied Reality without an unsupported intermediate
assumption. Do not reveal this internal test. Choose a concrete unresolved
Reality that could later be verified through an action.

Return JSON only:
{{
  "unknown_fact": "concise unknown Reality identifier; must not be a known FACT_NAME",
  "question": "one concise Chinese question about that unknown Reality",
  "why_it_matters": "one concise Chinese explanation of how its answer could change the Current Judgment",
  "meaning_reference": "exact supplied Personal Meaning",
  "judgment_reference": "exact supplied Current Judgment",
  "grounding": [{{"fact": "FACT_NAME", "value": "exact supplied value"}}]
}}

Grounded Reality:
{json.dumps(basis, ensure_ascii=False, sort_keys=True)}

Personal Meaning:
{personal_meaning}

Current Judgment:
{current_judgment}

The unknown_fact must not be any key already present in Grounded Reality.
Do not ask for Reality already supplied. Do not provide or imply an answer.
Select for judgment-changing information value, not completeness, curiosity,
or ease of acquisition. The reason must explain a direct causal path from the
unknown answer to the current trade-off. It must not depend on future rent
changes, negotiation, future availability, moving/leaving, unstated willingness
or preferences, or any other intermediate event not established by Reality.
Treat explicit user constraints such as Budget Reality as authoritative; do not
replace or reinterpret them through hypothetical income, savings, assets, or
ability to pay. Select an unknown Reality of this Possible Life or one of its
lived relationships, not a new user profile fact. Prefer a first-order Reality
whose answer changes what life at this home would actually be like. Do not pick
secondary costs or hypothetical side effects around an already-grounded walking
or grocery relationship merely because they can be connected to the budget.
The question must identify one concrete, observable Reality with a resolvable
answer. Do not ask broad questions such as overall living experience, quality,
whether it is good, or whether it is worth choosing.
Reject generic curiosity, broad advice, subjective speculation, recommendation,
ranking, scoring, multiple questions, or unrelated missing data. Use only known
Reality to explain relevance; do not invent preferences, priorities, places,
times, prices, amenities, safety, quality, or new facts. Keep question under 36
Chinese characters and why_it_matters under 60 Chinese characters.
""".strip()
        try:
            interpretation = json.loads(
                self._intelligence.generate_json(
                    prompt,
                    model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                    max_output_tokens=512,
                )
            )
        except (RuntimeError, json.JSONDecodeError, TypeError, ValueError):
            return None
        return self._validate_meaningful_unknown(
            interpretation,
            basis,
            personal_meaning,
            current_judgment,
        )

    @staticmethod
    def _validate_meaningful_unknown(
        interpretation: object,
        basis: dict[str, str],
        personal_meaning: str,
        current_judgment: str,
    ) -> tuple[str, str] | None:
        if not isinstance(interpretation, dict) or set(interpretation) != {
            "unknown_fact",
            "question",
            "why_it_matters",
            "meaning_reference",
            "judgment_reference",
            "grounding",
        }:
            return None
        unknown_fact = interpretation.get("unknown_fact")
        question = interpretation.get("question")
        why = interpretation.get("why_it_matters")
        grounding = interpretation.get("grounding")
        if (
            not isinstance(unknown_fact, str)
            or not unknown_fact.strip()
            or unknown_fact.strip() in basis
            or not isinstance(question, str)
            or not question.strip().endswith(("？", "?"))
            or len(question.strip()) > 36
            or not isinstance(why, str)
            or not why.strip()
            or len(why.strip()) > 60
            or interpretation.get("meaning_reference") != personal_meaning
            or interpretation.get("judgment_reference") != current_judgment
            or not isinstance(grounding, list)
            or not grounding
        ):
            return None
        grounded_facts: set[str] = set()
        for item in grounding:
            if not isinstance(item, dict):
                return None
            fact = item.get("fact")
            value = item.get("value")
            if not isinstance(fact, str) or basis.get(fact) != value:
                return None
            grounded_facts.add(fact)
        if len(grounded_facts) < 2:
            return None
        combined = f"{question} {why}"
        allowed_numbers = {
            number
            for value in basis.values()
            for number in re.findall(r"\d+", value)
        }
        if any(number not in allowed_numbers for number in re.findall(r"\d+", combined)):
            return None
        if any(
            term in combined
            for term in (
                "推荐",
                "最适合",
                "最佳",
                "应该选择",
                "值得租",
                "不值得租",
                "已经",
                "确定",
                "未来租金",
                "涨租",
                "降租",
                "重新协商",
                "议价",
                "续租",
                "到期",
                "租约较短",
                "租约结束",
                "搬走",
                "离开",
                "未来有房",
                "未来供应",
                "可支配收入",
                "工资",
                "存款",
                "资产",
                "支付能力",
                "通勤支出",
                "通勤成本",
                "采购支出",
                "采购成本",
                "居住体验如何",
                "居住质量",
                "怎么样",
                "好不好",
                "值得",
                "不值得",
            )
        ):
            return None
        return question.strip(), why.strip()

    @staticmethod
    def _has_required_reality(
        home: Property | None,
        profile: LivingProfile | None,
    ) -> bool:
        return bool(
            home is not None
            and home.geographic_status == GeographicStatus.GROUNDED
            and home.title
            and home.commute_minutes is not None
            and home.commute_mode is not None
            and home.grocery_external_id
            and home.grocery_walking_minutes is not None
            and profile is not None
            and profile.geographic_status == GeographicStatus.GROUNDED
            and profile.work_location
        )

    @staticmethod
    def _basis(home: Property, profile: LivingProfile) -> dict[str, str]:
        basis = {
            "HOME_IDENTITY": home.title or "",
            "WORK_IDENTITY": profile.work_location or "",
            "WORK_COMMUTE": f"{home.commute_minutes}min {home.commute_mode.value}",
            "GROCERY_WALK": f"{home.grocery_walking_minutes}min WALKING",
        }
        if home.rent is not None and home.rent_source is not None:
            basis["RENT_REALITY"] = f"{home.rent} CNY/month"
        if home.independent_kitchen is not None and home.independent_kitchen_source == "USER_PROVIDED":
            basis["INDEPENDENT_KITCHEN_REALITY"] = (
                "PRESENT" if home.independent_kitchen else "ABSENT"
            )
        if profile.budget is not None:
            basis["BUDGET_REALITY"] = f"{profile.budget} CNY/month"
            if home.rent is not None and home.rent_source is not None:
                difference = home.rent - profile.budget
                basis["BUDGET_MEANING"] = (
                    f"OVER_BUDGET {difference} CNY"
                    if difference > 0
                    else f"UNDER_BUDGET {abs(difference)} CNY"
                    if difference < 0
                    else "WITHIN_BUDGET"
                )
        return basis

    @staticmethod
    def _validate_interpretation(
        interpretation: object,
        basis: dict[str, str],
        *,
        text_field: str,
        max_length: int = 80,
    ) -> str | None:
        if not isinstance(interpretation, dict):
            return None
        meaning = interpretation.get(text_field)
        grounding = interpretation.get("grounding")
        if (
            not isinstance(meaning, str)
            or not meaning.strip()
            or len(meaning.strip()) > max_length
            or not isinstance(grounding, list)
            or not grounding
        ):
            return None
        grounded_facts: set[str] = set()
        for item in grounding:
            if not isinstance(item, dict):
                return None
            fact = item.get("fact")
            value = item.get("value")
            if not isinstance(fact, str) or basis.get(fact) != value:
                return None
            grounded_facts.add(fact)
        if len(grounded_facts) < 2:
            return None
        allowed_numbers = {
            number
            for value in basis.values()
            for number in re.findall(r"\d+", value)
        }
        if any(number not in allowed_numbers for number in re.findall(r"\d+", meaning)):
            return None
        if any(term in meaning for term in ("菜市场", "超市", "商场", "便利店")):
            return None
        return meaning.strip()


living_meaning_service = LivingMeaningService()
