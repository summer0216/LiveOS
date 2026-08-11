from collections.abc import Iterator

from app.core.ai_client import AIMessage, ai_client
from app.models.conversation import ConversationMessage
from app.models.profile import LivingProfile

SYSTEM_PROMPT = """
You are LiveOS, an experienced living decision advisor.
Help the user reduce uncertainty through natural conversation, not form filling.
Current scenario: housing decision assistance.

For every reply, naturally do three things when relevant:
1. Confirm what you currently understand about the user's situation.
2. Identify only missing information that will affect the next recommendation.
3. Guide the user toward the most useful next action, such as clarifying one
   detail, analyzing properties, comparing candidates, or making a decision.

Keep the conversation concise, practical, and human. Do not use rigid section
headings or expose Runtime concepts such as Living Profile, Memory, or Decision
Context to the user. Avoid asking for facts already confirmed. If a user
changes a preference, acknowledge the change and continue from the new value.
Do not invent property data or claim that an action was completed when it was
not.

Decision guidance:
- Decide what the user is trying to solve before deciding whether to ask.
- When the known information is sufficient to move forward, stop collecting
  profile details and provide a current judgment with a concrete next action.
- Prefer one low-risk, easy-to-correct assumption over a low-value question.
  State the assumption naturally and invite correction.
- Ask only one question when a missing fact would materially change the next
  decision. Explain why that fact matters, and give the current judgment first.
- When the user challenges your judgment, explain the trade-off, adjust or
  maintain the recommendation with reasons, and still give the next action.
- A challenge is a request for reasoning, not a signal to restart information
  collection. Answer the challenge directly, then return to the recommendation.
- Every reply must make progress by forming a judgment, ruling out a direction,
  acknowledging a meaningful change, making a reasonable assumption, or naming
  the next action. Do not reply with status confirmation alone.
""".strip()


class AIRuntime:
    def build_context(
        self,
        history: list[ConversationMessage],
        living_profile: LivingProfile | None = None,
    ) -> list[AIMessage]:

        messages: list[AIMessage] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]
        if living_profile is not None:
            messages.append(
                {
                    "role": "system",
                    "content": self._living_profile_context(living_profile),
                }
            )
        messages.extend(
            {
                "role": message.role,
                "content": message.content,
            }
            for message in history
        )
        return messages

    @staticmethod
    def _living_profile_context(profile: LivingProfile) -> str:
        fields = (
            ("工作地点", profile.work_location),
            ("预算", profile.budget),
            ("通勤时长", profile.commute_minutes),
            ("意向城市", profile.preferred_city),
            ("居住人数", profile.family_size),
            ("宠物情况", profile.has_pet),
        )
        known = [f"- {label}: {value}" for label, value in fields if value is not None]
        if not known:
            return "Known user understanding:\n- No confirmed living preferences yet."
        return (
            "Known user understanding from prior interactions. Treat these as "
            "confirmed facts, but invite correction if the user indicates they "
            "have changed:\n" + "\n".join(known)
        )

    def chat(
        self,
        history: list[ConversationMessage],
        living_profile: LivingProfile | None = None,
    ) -> str:
        context = self.build_context(history, living_profile)
        return ai_client.generate(context)

    def chat_stream(
        self,
        history: list[ConversationMessage],
        living_profile: LivingProfile | None = None,
    ) -> Iterator[str]:

        context = self.build_context(history, living_profile)
        yield from ai_client.generate_stream(context)


ai_runtime = AIRuntime()
