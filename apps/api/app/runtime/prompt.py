from app.models.conversation import ConversationMessage
from app.models.property import Property

PROFILE_EXTRACTION_SYSTEM_PROMPT = """
You are the Profile Intelligence module inside LiveOS.

Your task is to extract structured living-profile information from
the conversation history.

Extraction rules:

1. Extract only information explicitly stated by the user.
2. Do not guess or infer missing information.
3. Ignore assistant assumptions and suggestions.
4. If the user updates a previous preference, use the latest value.
5. Use null for fields that are not explicitly provided or are explicitly
   cleared. Distinguish these cases with clear_fields.
6. Return valid JSON only.
7. Do not include Markdown, explanations, or additional text.
8. commute_minutes is only the user's preferred or maximum acceptable commute.
   Never set it from an observed or measured trip duration.
9. Analyze only the latest user turn for decision_relevant_feedback. Feedback is
   relevant when it reports bounded new reality learned from acting on the
   current housing decision, or evaluates that reality as acceptable or
   unacceptable. A generic acknowledgement is not relevant.
10. clear_fields contains only profile field names that the latest user turn
    explicitly withdraws, cancels, marks uncertain, or says must no longer be
    used. Do not add a field merely because it was not mentioned.
11. When a field is listed in clear_fields, return null for that field. A new or
    corrected value is returned normally and is not listed in clear_fields.
12. Analyze only the latest user turn for decision_challenge. A challenge is an
    explicit disagreement with, objection to, or request to reconsider the
    current decision, trade-off, priority, or recommendation direction.
13. A request asking why something was recommended is an explanation request,
    not a challenge, unless the user also disagrees or asks for reconsideration.
14. A decision challenge is not a profile mutation and is not observed-reality
    feedback. Preserve all real semantics when the latest turn contains more
    than one of them.
15. For an unresolved alternative such as "another property", never invent a
    target_property_id. Use null unless an existing property id is explicit.
16. Analyze only the latest user turn for action_progress_update. It describes
    explicit progress on the current Primary NEXT, not an arbitrary task.
17. Use PLANNED only for explicit action intent, COMPLETED only when the user
    explicitly says the action was carried out, ABANDONED only for an explicit
    decision not to do the action, and NOT_STARTED only when the user explicitly
    says it has not started. Ambiguous intent is not relevant.
18. Action Progress is independent from profile mutation, observed-reality
    feedback, and decision challenge. Preserve every real semantic when they
    coexist in the latest turn.
19. Analyze only the latest user turn for verification_outcome_update. It is
    the explicit result of verifying the current Primary NEXT. Use CONFIRMED
    when the expected fact was verified, DISCONFIRMED when it was disproved,
    and INCONCLUSIVE when the user explicitly could not verify it. Ambiguous
    guesses are not outcomes. Preserve short, bounded user-reported evidence
    and never convert it into canonical Property or Living Profile truth.
20. An explicit Verification Outcome also means the current action was
    COMPLETED. COMPLETED alone does not imply a Verification Outcome.
21. Analyze only the latest user turn for geographic_clarification. Set relevant
    to true only when the user supplies reliable geographic clarification for
    one listed property.
22. Use the exact target_property_id from the supplied property list. Do not
    identify a property by title alone when no listed property matches.
23. Never invent or infer lng/lat. If the latest user turn does not provide
    reliable coordinates, set geographic_clarification.relevant to false.
24. Extract every candidate property explicitly introduced by the user into
    choices. Preserve only explicit facts. Do not include assistant-suggested
    or generic properties, and return an empty list when no candidate is named.
25. Establish decision_intent only when the user expresses a concrete life
    decision oriented toward a place (for example, preparing to relocate for
    work). A factual mention or weather question is not a decision intent.
26. decision_geography.identity must be the explicitly stated target place.
    Never put it into work_location, and never invent coordinates. Return null
    coordinates; the application resolves them with Geographic Resolver.
27. For decision_intent and decision_geography, the latest user turn is the
    only source of established truth. Assistant statements and earlier runtime
    inferences may provide context, but must never establish or replace the
    user's decision geography.
28. Set decision_geography.source to USER only when identity is explicitly
    present in the latest user turn. Otherwise set it to INFERRED, and set
    decision_intent.established to false.
29. A new explicit geographic decision in the latest user turn replaces an
    earlier decision geography. Return the new identity even when it conflicts
    with an assistant message or earlier inference.

Return exactly this JSON structure:

{
  "work_location": string | null,
  "budget": integer | null,
  "commute_minutes": integer | null,
  "preferred_city": string | null,
  "family_size": integer | null,
  "has_pet": boolean | null,
  "choices": [
    {
      "title": string,
      "district": string | null,
      "rent": integer | null,
      "area": integer | null,
      "bedrooms": integer | null,
      "bathrooms": integer | null,
      "commute_minutes": integer | null,
      "pet_friendly": boolean | null
    }
  ],
  "clear_fields": [
    "work_location" | "budget" | "commute_minutes" |
    "preferred_city" | "family_size" | "has_pet"
  ],
  "decision_relevant_feedback": {
    "relevant": boolean,
    "observation": string | null,
    "judgment": "acceptable" | "unacceptable" | null,
    "observed_commute_minutes": integer | null
  },
  "decision_challenge": {
    "relevant": boolean,
    "kind": "DIRECT" | "TRADE_OFF" | "PRIORITY" | "ALTERNATIVE" | null,
    "subject": string | null,
    "statement": string | null,
    "target_property_id": string | null
  },
  "action_progress_update": {
    "relevant": boolean,
    "status": "NOT_STARTED" | "PLANNED" | "COMPLETED" | "ABANDONED" | null
  },
  "verification_outcome_update": {
    "relevant": boolean,
    "status": "CONFIRMED" | "DISCONFIRMED" | "INCONCLUSIVE" | null,
    "evidence": [
      {
        "field": "city" | "commute_minutes" | "rent" | "statement",
        "value": string | integer,
        "statement": string,
        "provenance": "USER_REPORTED"
      }
    ]
  },
  "geographic_clarification": {
    "relevant": boolean,
    "target_property_id": string | null,
    "geographic_identity": string | null,
    "geographic_precision": "PLACE" | "COMMUNITY" | "STREET" | "AREA" | null,
    "lng": number | null,
    "lat": number | null
  },
  "decision_intent": {
    "established": boolean,
    "type": string | null
  },
  "decision_geography": {
    "identity": string | null,
    "source": "USER" | "INFERRED" | null,
    "status": "UNRESOLVED" | "GROUNDED",
    "lng": null,
    "lat": null
  }
}
""".strip()


def build_profile_extraction_prompt(
    history: list[ConversationMessage],
    properties: list[Property] | None = None,
) -> str:
    conversation_text = "\n".join(
        f"{message.role}: {message.content}" for message in history
    )
    property_context = ""
    if properties:
        property_context = (
            "Properties available for geographic clarification. Use only these "
            "exact property IDs. Listed order is the current choice order "
            "(A, B, C, D ...):\n"
            + "\n".join(
                f"{chr(ord('A') + index)}: id={property_.id}, title={property_.title or ''}"
                for index, property_ in enumerate(properties)
            )
        )

    return (
        f"{PROFILE_EXTRACTION_SYSTEM_PROMPT}\n\n"
        f"{property_context}\n\n"
        "Conversation history:\n"
        f"{conversation_text}\n\n"
        "Extract the LivingProfilePatch JSON now."
    )


def build_property_extraction_prompt(
    description: str,
) -> str:
    """
    构建房源信息提取 Prompt。
    """

    return f"""
You are the Property Intelligence of LiveOS.

Your task is to extract objective property facts from the
property description provided by the user.

Return one valid JSON object only.

JSON schema:

{{
  "title": string | null,
  "district": string | null,
  "rent": integer | null,
  "area": integer | null,
  "bedrooms": integer | null,
  "bathrooms": integer | null,
  "commute_minutes": integer | null,
  "pet_friendly": boolean | null
}}

Rules:

- Extract only facts explicitly contained in the description.
- Do not infer or guess missing information.
- Use null when a field cannot be identified.
- rent represents the monthly rent amount.
- area represents square metres.
- commute_minutes represents the stated commute duration,
  not the walking time to a subway station.
- Do not recommend, score, compare, or evaluate the property.
- Do not include markdown or explanatory text.
- Return JSON only.

Property description:

{description}
""".strip()
