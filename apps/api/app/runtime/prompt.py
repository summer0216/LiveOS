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
5. Use null for fields that are not explicitly provided.
6. Return valid JSON only.
7. Do not include Markdown, explanations, or additional text.

Return exactly this JSON structure:

{
  "work_location": string | null,
  "budget": integer | null,
  "commute_minutes": integer | null,
  "preferred_city": string | null,
  "family_size": integer | null,
  "has_pet": boolean | null
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
