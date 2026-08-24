from app.models.conversation import ConversationMessage

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

Return exactly this JSON structure:

{
  "work_location": string | null,
  "budget": integer | null,
  "commute_minutes": integer | null,
  "preferred_city": string | null,
  "family_size": integer | null,
  "has_pet": boolean | null,
  "clear_fields": [
    "work_location" | "budget" | "commute_minutes" |
    "preferred_city" | "family_size" | "has_pet"
  ],
  "decision_relevant_feedback": {
    "relevant": boolean,
    "observation": string | null,
    "judgment": "acceptable" | "unacceptable" | null,
    "observed_commute_minutes": integer | null
  }
}
""".strip()


def build_profile_extraction_prompt(
    history: list[ConversationMessage],
) -> str:
    conversation_text = "\n".join(
        f"{message.role}: {message.content}" for message in history
    )

    return (
        f"{PROFILE_EXTRACTION_SYSTEM_PROMPT}\n\n"
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
