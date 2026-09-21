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
        if (
            home.current_judgment
            and home.current_judgment_state_hash == judgment_hash
        ):
            return LivingMeaningResult(
                "UPDATED" if meaning_updated else "EXISTING",
                home,
            )
        judgment = self._generate_judgment(basis, home.living_meaning)
        if judgment is None:
            return LivingMeaningResult("INVALID_JUDGMENT", home)
        updated = self._properties.update_current_judgment(
            property_id,
            conversation_id,
            judgment=judgment,
            state_hash=judgment_hash,
        )
        return LivingMeaningResult("UPDATED" if updated else "NOT_FOUND", updated)

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
