from dataclasses import asdict

from app.models.conversation import ConversationMessage
from app.models.environment_eligibility import (
    EnvironmentAttention,
    EnvironmentEligibilityResult,
    EnvironmentProjectionEligibility,
)
from app.models.property import GeographicStatus, Property
from app.models.reality_evidence import RealityAdmission, RealityEvidence
from app.services.place_context_reality import (
    PlaceContextRealityService,
    is_admitted_nearby_reality,
)


def environment_attention_context(properties: list[Property]) -> list[dict]:
    """Expose only admitted candidates to the existing expression interpreter."""
    return [
        {"property_id": home.id, "places": [
            {key: item[key] for key in ("external_id", "name", "category", "type_code")}
            for item in home.place_context or []
            if is_admitted_nearby_reality(item, home)
            and item.get("external_id")
            and item["evidence"].get("source_record_id") == item["external_id"]
        ]}
        for home in properties if home.geographic_status == GeographicStatus.GROUNDED
    ]


def eligible_environment(
    interpretation: object,
    *,
    conversation_id: str | None,
    history: list[ConversationMessage],
    user_text: str,
    properties: list[Property],
    focused_property_id: str | None,
    attention_property_id: str | None,
) -> tuple[EnvironmentProjectionEligibility, ...]:
    """Validate one optional result from the existing Conversation interpretation.

    Category semantics come from that interpretation, never frontend keywords.
    Focus only binds Place: an explicit current-user interest is also required.
    Missing, ambiguous or stale associations fail closed.
    """
    if not isinstance(interpretation, dict) or set(interpretation) != {
        "property_id", "category", "type_codes", "quote", "environment_ids",
    }:
        return ()
    if not conversation_id or not history:
        return ()
    turn = history[-1]
    quote = interpretation["quote"]
    category = interpretation["category"]
    ids = interpretation["environment_ids"]
    type_codes = interpretation["type_codes"]
    if (
        turn.role != "user" or turn.content != user_text
        or isinstance(turn.id, bool) or not isinstance(turn.id, int) or turn.id <= 0
        or not isinstance(quote, str) or not quote.strip() or quote not in user_text
        or not isinstance(category, str)
        or category not in PlaceContextRealityService.category_types
        or not isinstance(type_codes, list) or not type_codes
        or any(code not in PlaceContextRealityService.category_types[category] for code in type_codes)
        or not isinstance(ids, list)
        or len(ids) > PlaceContextRealityService.max_per_category
        or any(not isinstance(item, str) or not item.strip() for item in ids)
        or len(set(ids)) != len(ids)
    ):
        return ()
    property_id = interpretation["property_id"]
    # A conflicting explicit attention target cannot be overridden by map Focus.
    target = attention_property_id or focused_property_id
    homes = [home for home in properties if (
        home.id == property_id == target
        and home.conversation_id == conversation_id
        and home.geographic_status == GeographicStatus.GROUNDED
        and home.geographic_identity and home.lng is not None and home.lat is not None
    )]
    if len(homes) != 1:
        return ()
    home = homes[0]
    # Keep the explicit Metro attention unchanged. Admitted tram stations are
    # related rail evidence, not Metro facts and not a reason to include buses.
    metro_attention = category == "TRANSIT" and "150500" in type_codes
    candidate_ids = list(ids)
    if metro_attention:
        for item in home.place_context or []:
            if (
                isinstance(item, dict) and item.get("category") == "TRANSIT"
                and item.get("type_code") == "150705"
                and isinstance(item.get("external_id"), str) and item["external_id"].strip()
                and is_admitted_nearby_reality(item, home)
                and item["external_id"] not in candidate_ids
            ):
                candidate_ids.append(item["external_id"])
    result = []
    for external_id in candidate_ids:
        matches = [item for item in home.place_context or [] if (
            isinstance(item, dict) and item.get("external_id") == external_id
        )]
        if len(matches) != 1:
            return ()
        item = matches[0]
        direct = item.get("category") == category and item.get("type_code") in type_codes
        supplement = metro_attention and item.get("category") == "TRANSIT" and item.get("type_code") == "150705"
        if not direct and not supplement:
            continue
        if not is_admitted_nearby_reality(item, home):
            return ()
        evidence = RealityEvidence.from_mapping(item["evidence"])
        admission = RealityAdmission.from_mapping(item["admission"])
        if evidence is None or admission is None or evidence.source_record_id != external_id:
            return ()
        result.append(EnvironmentProjectionEligibility(
            attention=EnvironmentAttention(
                conversation_id=conversation_id,
                source_user_turn_id=turn.id,
                source_quote=quote,
                property_id=home.id,
                property_identity=home.geographic_identity,
                property_lng=home.lng,
                property_lat=home.lat,
                category=category,
                type_codes=tuple(type_codes),
                place_binding_source="USER_ATTENTION" if attention_property_id else "FOCUS",
            ),
            environment_external_id=external_id,
            environment_identity=item["identity"],
            environment_type_code=item["type_code"],
            evidence=evidence,
            admission=admission,
            relevance_basis="USER_EXPRESSED_CATEGORY" if direct else "RELATED_RAIL_SUPPLEMENT",
        ))
    return tuple(result)


def environment_attention_snapshot(result: EnvironmentEligibilityResult) -> dict | None:
    """Persist the validated user interest, not an enduring grant to project evidence."""
    if not result.items:
        return None
    return {
        "attention": {**asdict(result.items[0].attention),
                      "type_codes": list(result.items[0].attention.type_codes)},
        "environment_ids": [item.environment_external_id for item in result.items
                            if item.relevance_basis == "USER_EXPRESSED_CATEGORY"],
    }


def resume_environment_eligibility(
    conversation_id: str, history: list[ConversationMessage], properties: list[Property],
) -> EnvironmentEligibilityResult | None:
    """Revalidate the latest user turn against current admitted evidence, without inference."""
    turns = [turn for turn in history if turn.role == "user"]
    if not turns or not isinstance(turns[-1].id, int):
        return None
    turn = turns[-1]
    empty = EnvironmentEligibilityResult(conversation_id, turn.id)
    snapshot = turn.environment_attention
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("attention"), dict):
        return empty
    attention = snapshot["attention"]
    if (attention.get("conversation_id") != conversation_id
        or attention.get("source_user_turn_id") != turn.id
        or attention.get("place_binding_source") not in {"FOCUS", "USER_ATTENTION"}):
        return empty
    home = next((home for home in properties if home.id == attention.get("property_id")), None)
    if (home is None or home.geographic_identity != attention.get("property_identity")
        or home.lng != attention.get("property_lng") or home.lat != attention.get("property_lat")):
        return empty
    interpretation = {
        "property_id": home.id, "category": attention.get("category"),
        "type_codes": attention.get("type_codes"),
        "quote": attention.get("source_quote"), "environment_ids": snapshot.get("environment_ids"),
    }
    items = eligible_environment(
        interpretation, conversation_id=conversation_id, history=[turn], user_text=turn.content,
        properties=properties,
        focused_property_id=home.id if attention["place_binding_source"] == "FOCUS" else None,
        attention_property_id=home.id if attention["place_binding_source"] == "USER_ATTENTION" else None,
    )
    return EnvironmentEligibilityResult(conversation_id, turn.id, items)
