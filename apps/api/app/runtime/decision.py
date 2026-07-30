import json

from app.schemas.decision import DecisionInput

DECISION_SYSTEM_PROMPT = """
You are the Decision Intelligence module inside LiveOS.

Use only the supplied Living Profile and Property fields.
Select exactly one real Property id when a valid recommendation is possible.
Return a concise user-facing summary, 1 to 4 reasons, 0 to 3 genuine
trade-offs, and confidence from 0.0 to 1.0.

Never invent location facts, schools, transit distance, neighbourhood details,
condition, market trends, investment advice, scores, rankings, or facts absent
from the input. Do not reveal chain of thought.

Return exactly one JSON object with this structure:
{
  "status": "waiting" | "ready",
  "summary": string | null,
  "best_property_id": string | null,
  "reasons": [{"title": string, "description": string}],
  "trade_offs": [{"title": string, "description": string}],
  "confidence": number | null
}

For waiting, best_property_id must be null and reasons and trade_offs must be
empty. For ready, summary and best_property_id must be non-empty and reasons
must contain at least one item.
""".strip()


def build_decision_prompt(decision_input: DecisionInput) -> str:
    property_count = len(decision_input.properties)
    comparison_instruction = (
        "There is one candidate. Describe a match against the Living Profile "
        "without claiming that multiple properties were compared, and state "
        "real information limitations when relevant."
        if property_count == 1
        else (
            "Compare the supplied candidates, choose one real Property id, "
            "and describe only trade-offs supported by their actual fields."
        )
    )
    input_json = json.dumps(
        decision_input.model_dump(mode="json"),
        ensure_ascii=False,
    )

    return (
        f"{DECISION_SYSTEM_PROMPT}\n\n"
        f"{comparison_instruction}\n\n"
        "Decision input:\n"
        f"{input_json}\n\n"
        "Return the Decision JSON now."
    )
