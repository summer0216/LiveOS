from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.core.ai_client import AIClient, ai_client
from app.core.config import settings
from app.models.property import GeographicStatus, Property
from app.services.property_manager import PropertyManager, property_manager


@dataclass(frozen=True)
class PlaceUnderstandingResult:
    status: str
    property: Property | None = None


class PlaceUnderstandingService:
    version = "v0.3-grounded-place-model"
    pattern_version = "v0.2-grounded-pattern"

    def __init__(
        self, *, properties: PropertyManager = property_manager,
        intelligence: AIClient = ai_client,
    ) -> None:
        self._properties = properties
        self._intelligence = intelligence

    def form(self, conversation_id: str, property_id: str) -> PlaceUnderstandingResult:
        home = self._properties.get_scoped(property_id, conversation_id)
        if (
            home is None or home.geographic_status != GeographicStatus.GROUNDED
            or home.lng is None or home.lat is None or not home.geographic_identity
        ):
            return PlaceUnderstandingResult("INSUFFICIENT_REALITY", home)
        places = [
            {key: item[key] for key in (
                "category", "external_id", "name", "identity", "type_code",
                "lng", "lat", "distance_m", "walking_minutes",
                "anchor_candidate", "co_located_with",
            )}
            for item in (home.place_context or [])
            if item.get("structure_version") == 2
            and all(key in item for key in (
                "category", "external_id", "name", "identity", "type_code",
                "lng", "lat", "distance_m", "walking_minutes",
                "anchor_candidate", "co_located_with",
            ))
            and item.get("external_id") and item.get("name")
            and isinstance(item.get("lng"), (int, float))
            and isinstance(item.get("lat"), (int, float))
        ]
        if len(places) < 2:
            return PlaceUnderstandingResult("INSUFFICIENT_REALITY", home)
        basis = {
            "home": {
                "identity": home.geographic_identity,
                "lng": home.lng,
                "lat": home.lat,
            },
            "places": places,
        }
        fingerprint = hashlib.sha256(json.dumps(
            {"version": self.version, "basis": basis},
            ensure_ascii=False, sort_keys=True,
        ).encode()).hexdigest()
        if (home.place_understanding or {}).get("reality_hash") == fingerprint:
            return PlaceUnderstandingResult("EXISTING", home)

        reusable_fingerprints = {
            hashlib.sha256(json.dumps(
                {"version": version, "basis": basis},
                ensure_ascii=False, sort_keys=True,
            ).encode()).hexdigest()
            for version in (self.pattern_version, "v0.3-place-model")
        }
        previous = home.place_understanding or {}
        output = None
        if previous.get("reality_hash") in reusable_fingerprints:
            candidate = {
                "claims": previous.get("claims"),
                "anchor_ids": previous.get("anchor_ids"),
            }
            if self._valid_shape(candidate, places):
                output = candidate

        prompt = f"""
Recognize Place-level patterns across ONLY this grounded geographic Reality,
not a personal living recommendation or a POI-by-POI summary. Return JSON only:
{{"claims":[{{"text":"concise Chinese grounded Place pattern",
"evidence_ids":["exact provider external_id"]}}],
"anchor_ids":["exact provider external_id"]}}
Use 0-3 claims. Prefer synthesis across multiple places, functions, spatial
relationships, and proven Home-to-place walking relationships. A pattern may
describe coexistence, concentration, dispersion, or multiple layers of a
function only when the supplied facts support it. Do not merely enumerate
which individual POIs are near Home. If no defensible pattern emerges,
return empty claims and empty anchor_ids. Every claim must cite all grounded
places it relies on.
Use 0-2 anchor IDs only; they are optional and must belong to supplied anchor
candidates. Do not force a dominant anchor.
Describe observed coexistence and supplied spatial relationships only. A
Home-to-POI walking duration does not prove a POI-to-POI walking relationship.
Never invent pairwise distances or walking-network connections.
Each place's distance_m is ONLY its distance from the Home. A numeric distance
between two surrounding places is allowed ONLY when that exact pair and value
appears in co_located_with. For pairs not in co_located_with, describe their
presence near the Home without a pairwise distance.
Do not infer causality, quality, convenience, completeness, suitability,
neighborhood reputation, or unsupported local knowledge. No Personal Meaning.
Grounded Reality: {json.dumps(basis, ensure_ascii=False, sort_keys=True)}
""".strip()
        for attempt in range(0 if output is not None else 2):
            try:
                candidate = json.loads(self._intelligence.generate_json(
                    prompt, model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                    max_output_tokens=512,
                ))
            except (RuntimeError, TypeError, ValueError, json.JSONDecodeError):
                return PlaceUnderstandingResult("REJECTED", home)
            if not self._valid_shape(candidate, places):
                if attempt == 0:
                    prompt += "\nPrevious output failed schema/grounding-ID validation. Use only 0-2 anchor IDs and cited provider IDs."
                    continue
                return PlaceUnderstandingResult("REJECTED", home)
            if not candidate["claims"]:
                output = candidate
                break
            audit_prompt = f"""
Audit EVERY assertion in these Place Understanding claims against ONLY the
supplied grounded geographic Reality. Exact POI identity, category, location,
distance and proven walking time are usable. Co-location is not causality.
Reject unsupported qualitative claims about convenience, completeness,
quality, suitability, development or why facilities exist.
Separately decide whether at least ONE claim is a grounded Place-level pattern
integrating multiple Reality objects/functions or their spatial relationships,
rather than only restating or listing individual nearby POIs. A pattern can
remain descriptive; it must not become an evaluation or personal meaning.
Grounded Reality: {json.dumps(basis, ensure_ascii=False, sort_keys=True)}
Proposed claims: {json.dumps(candidate, ensure_ascii=False, sort_keys=True)}
Return JSON only: {{"supported":true or false,"unsupported_claims":["claim"],"place_pattern":true or false}}
""".strip()
            try:
                audit = json.loads(self._intelligence.generate_json(
                    audit_prompt, model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                    max_output_tokens=192,
                ))
            except (RuntimeError, TypeError, ValueError, json.JSONDecodeError):
                return PlaceUnderstandingResult("REJECTED", home)
            if (
                isinstance(audit, dict)
                and set(audit) == {"supported", "unsupported_claims", "place_pattern"}
                and audit["supported"] is True and audit["unsupported_claims"] == []
                and audit["place_pattern"] is True
            ):
                output = candidate
                break
            if attempt == 0:
                prompt += (
                    "\nPrevious claims failed grounded-Reality or Place-pattern audit. "
                    "Remove unsupported claims and replace fact enumeration with "
                    "a supported cross-Reality pattern, if one exists."
                )
        if output is None:
            return PlaceUnderstandingResult("REJECTED", home)
        place_model = self._form_place_model(basis, output, places)
        if place_model is False:
            return PlaceUnderstandingResult("REJECTED", home)
        understanding = {
            **output, "place_model": place_model, "reality_hash": fingerprint,
        }
        updated = self._properties.update_place_understanding(
            property_id, conversation_id, understanding,
        )
        return PlaceUnderstandingResult("UPDATED" if updated else "NOT_FOUND", updated)

    def _form_place_model(
        self, basis: dict, patterns: dict, places: list[dict],
    ) -> dict | None | bool:
        if len(patterns["claims"]) < 2:
            return None
        prompt = f"""
Synthesize at most ONE concise Chinese Place Model from these ACCEPTED,
grounded Place Patterns and their underlying geographic Reality. Answer what
kind of Place surrounds this Home, NOT whether it is good for this user.
Integrate the strongest supported patterns into one coherent description;
do not repeat the patterns one after another or enumerate named POIs.
Prefer one short sentence about supported functions and spatial coexistence.
If no coherent synthesis is
supported, return null.
Return JSON only, either null or:
{{"text":"one concise Place-level description",
"pattern_indices":[0,1],"evidence_ids":["exact provider external_id"]}}
pattern_indices must cite at least two supplied accepted patterns. evidence_ids
must cite their actual grounded provider POIs. Anchors are candidates, not a
required or dominant explanation. Coexistence is not causality. Do not infer
that any anchor candidate is the core, center, organizing force or cause of
this Place. Do not infer quality, convenience, maturity, suitability,
preferences, or Personal Meaning.
Grounded Reality: {json.dumps(basis, ensure_ascii=False, sort_keys=True)}
Accepted Patterns: {json.dumps(patterns, ensure_ascii=False, sort_keys=True)}
""".strip()
        for attempt in range(2):
            try:
                model = json.loads(self._intelligence.generate_json(
                    prompt, model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                    max_output_tokens=256,
                ))
            except (RuntimeError, TypeError, ValueError, json.JSONDecodeError):
                return False
            if model is None:
                return None
            if not self._valid_model(model, patterns, places):
                if attempt == 0:
                    prompt += "\nPrevious Place Model failed shape or evidence-reference validation. Use only accepted pattern indices and grounded POI IDs."
                    continue
                return False
            audit_prompt = f"""
Audit EVERY assertion in this proposed Place Model against BOTH the grounded
Reality and the accepted Place Patterns. Reject unsupported qualitative or
causal claims, invented distances, unproven walking relationships, and a
sentence that only repeats patterns sequentially rather than synthesizing a
coherent Place. Coexistence does not prove causality or quality.
An anchor candidate does not prove that a facility is the core, center,
dominant organizing force, or reason the Place formed. Reject such claims.
Reject a POI-by-POI rollcall even when each listed fact is true.
Grounded Reality: {json.dumps(basis, ensure_ascii=False, sort_keys=True)}
Accepted Patterns: {json.dumps(patterns, ensure_ascii=False, sort_keys=True)}
Proposed Place Model: {json.dumps(model, ensure_ascii=False, sort_keys=True)}
Return JSON only: {{"supported":true or false,"unsupported_claims":["claim"],"coherent_model":true or false}}
""".strip()
            try:
                audit = json.loads(self._intelligence.generate_json(
                    audit_prompt, model=settings.DECISION_SIGNAL_MODEL or "deepseek-chat",
                    max_output_tokens=192,
                ))
            except (RuntimeError, TypeError, ValueError, json.JSONDecodeError):
                return False
            if (
                isinstance(audit, dict)
                and set(audit) == {"supported", "unsupported_claims", "coherent_model"}
                and audit["supported"] is True
                and audit["unsupported_claims"] == []
                and audit["coherent_model"] is True
            ):
                return model
            if attempt == 0:
                prompt += "\nPrevious model failed grounded-Reality or coherence audit. Remove unsupported claims and synthesize only the accepted patterns."
        return False

    @staticmethod
    def _valid_model(model: object, patterns: dict, places: list[dict]) -> bool:
        if not isinstance(model, dict) or set(model) != {"text", "pattern_indices", "evidence_ids"}:
            return False
        text, indices, evidence = model["text"], model["pattern_indices"], model["evidence_ids"]
        if not isinstance(text, str) or not 0 < len(text.strip()) <= 140:
            return False
        if not isinstance(indices, list) or not all(type(index) is int for index in indices):
            return False
        if not 2 <= len(set(indices)) <= 3:
            return False
        if not all(0 <= index < len(patterns["claims"]) for index in indices):
            return False
        cited_ids = {
            external_id for index in indices
            for external_id in patterns["claims"][index]["evidence_ids"]
        }
        grounded_ids = {place["external_id"] for place in places}
        return (
            isinstance(evidence, list) and len(evidence) >= 2
            and all(isinstance(external_id, str) for external_id in evidence)
            and set(evidence) <= cited_ids & grounded_ids
        )

    @staticmethod
    def _valid_shape(output: object, places: list[dict]) -> bool:
        if not isinstance(output, dict) or set(output) != {"claims", "anchor_ids"}:
            return False
        claims, anchor_ids = output["claims"], output["anchor_ids"]
        if not isinstance(claims, list) or not 0 <= len(claims) <= 3:
            return False
        if not isinstance(anchor_ids, list) or not all(isinstance(x, str) for x in anchor_ids):
            return False
        ids = {item["external_id"] for item in places}
        anchor_candidates = {item["external_id"] for item in places if item["anchor_candidate"]}
        if len(anchor_ids) > 2 or not set(anchor_ids) <= anchor_candidates:
            return False
        if not claims and anchor_ids:
            return False
        return all(
            isinstance(claim, dict) and set(claim) == {"text", "evidence_ids"}
            and isinstance(claim["text"], str)
            and 0 < len(claim["text"].strip()) <= 120
            and isinstance(claim["evidence_ids"], list)
            and 1 <= len(claim["evidence_ids"]) <= 6
            and all(isinstance(x, str) and x in ids for x in claim["evidence_ids"])
            for claim in claims
        )


place_understanding_service = PlaceUnderstandingService()
