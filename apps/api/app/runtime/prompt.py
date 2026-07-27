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
