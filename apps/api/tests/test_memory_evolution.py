import json
from collections.abc import Iterator
from uuid import UUID

import pytest

from app.models.decision_memory import (
    DecisionMemory,
    DecisionMemoryCandidate,
    DecisionMemoryCategory,
)
from app.models.profile_patch import LivingProfilePatch
from app.models.property import Property
from app.runtime.memory_evolution import MemoryEvolutionCandidate
from app.schemas.decision import DecisionReason, DecisionResult
from app.services.decision_memory_extraction_service import (
    DecisionMemoryExtractionService,
)
from app.services.decision_memory_service import (
    DecisionMemoryService,
    decision_memory_service,
)
from app.services.decision_record_service import decision_record_service
from app.services.profile_manager import profile_manager
from app.services.property_manager import property_manager
from app.stores.decision_memory_store import (
    DecisionMemoryStore,
    decision_memory_store,
)

CONVERSATION_IDS = (
    "evolution-main",
    "evolution-other",
    "evolution-failure",
)


class FakeJSONClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.call_count = 0
        self.prompts: list[str] = []

    def generate_json(self, prompt: str) -> str:
        self.call_count += 1
        self.prompts.append(prompt)
        return self.response


class FailingReplaceStore(DecisionMemoryStore):
    def replace_conversation(
        self,
        conversation_id: str,
        memories: list[DecisionMemory],
    ) -> list[DecisionMemory]:
        raise RuntimeError("store unavailable")


@pytest.fixture(autouse=True)
def clean_evolution_data() -> Iterator[None]:
    decision_memory_store.clear()
    for conversation_id in CONVERSATION_IDS:
        decision_record_service.delete_conversation(conversation_id)
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)

    yield

    decision_memory_store.clear()
    for conversation_id in CONVERSATION_IDS:
        decision_record_service.delete_conversation(conversation_id)
        profile_manager.delete(conversation_id)
        property_manager.delete_conversation(conversation_id)


def save_record(conversation_id: str, summary: str) -> str:
    record = decision_record_service.save(
        conversation_id,
        DecisionResult(
            status="ready",
            summary=summary,
            best_property_id="property-a",
            reasons=[
                DecisionReason(
                    title="当前依据",
                    description="当前事实支持这一选择。",
                ),
            ],
            trade_offs=[],
            confidence=0.8,
        ),
    )
    return record.id


def memory_candidate(
    record_ids: list[str],
    content: str,
) -> DecisionMemoryCandidate:
    return DecisionMemoryCandidate(
        category=DecisionMemoryCategory.PREFERENCE,
        content=content,
        confidence=0.8,
        evidence_record_ids=[UUID(record_id) for record_id in record_ids],
    )


def test_reinforcement_preserves_identity_and_adds_evidence() -> None:
    service = DecisionMemoryService(DecisionMemoryStore())
    record_ids = [
        save_record("evolution-main", f"Decision {index}") for index in range(3)
    ]
    existing = service.save_candidate(
        "evolution-main",
        memory_candidate(record_ids[:2], "用户长期偏好较短通勤。"),
    )

    evolved = service.evolve_candidates(
        "evolution-main",
        [
            MemoryEvolutionCandidate(
                memory_id=existing.id,
                category=existing.category,
                content=existing.content,
                confidence=0.9,
                evidence_record_ids=[
                    UUID(record_ids[1]),
                    UUID(record_ids[2]),
                ],
            ),
        ],
    )[0]

    assert evolved.id == existing.id
    assert evolved.confidence == 0.9
    assert evolved.evidence_record_ids == [UUID(record_id) for record_id in record_ids]


def test_update_replaces_content_without_changing_schema_or_identity() -> None:
    service = DecisionMemoryService(DecisionMemoryStore())
    record_ids = [
        save_record("evolution-main", f"Decision {index}") for index in range(3)
    ]
    existing = service.save_candidate(
        "evolution-main",
        memory_candidate(record_ids[:2], "用户长期优先较低租金。"),
    )

    evolved = service.evolve_candidates(
        "evolution-main",
        [
            MemoryEvolutionCandidate(
                memory_id=existing.id,
                category=existing.category,
                content="用户当前长期优先较短通勤。",
                confidence=0.75,
                evidence_record_ids=[
                    UUID(record_ids[1]),
                    UUID(record_ids[2]),
                ],
            ),
        ],
    )[0]

    assert evolved.id == existing.id
    assert evolved.content == "用户当前长期优先较短通勤。"
    assert evolved.confidence == 0.75
    assert evolved.created_at == existing.created_at
    assert len(service.list_memories("evolution-main")) == 1


def test_refresh_prompt_enforces_current_facts_priority_and_one_call() -> None:
    record_ids = [
        save_record("evolution-main", f"Decision {index}") for index in range(2)
    ]
    profile_manager.merge(
        "evolution-main",
        LivingProfilePatch(budget=6000, commute_minutes=30),
        latest_insights=[],
    )
    property_manager.create(
        "evolution-main",
        Property(title="当前房源", rent=5800, commute_minutes=25),
    )
    response = json.dumps(
        {
            "candidates": [
                {
                    "memory_id": None,
                    "category": "preference",
                    "content": "用户持续偏好较短通勤。",
                    "confidence": 0.82,
                    "evidence_record_ids": record_ids,
                },
            ],
        },
        ensure_ascii=False,
    )
    client = FakeJSONClient(response)
    service = DecisionMemoryExtractionService(
        decision_records=decision_record_service,
        memory_service=decision_memory_service,
        json_client=client,
        profile_source=profile_manager,
        property_source=property_manager,
    )

    result = service.extract("evolution-main")

    assert result.saved_count == 1
    assert client.call_count == 1
    assert "Current Facts have the highest priority" in client.prompts[0]
    assert '"budget": 6000' in client.prompts[0]
    assert '"rent": 5800' in client.prompts[0]
    assert client.prompts[0].index("CURRENT FACTS") < client.prompts[0].index(
        "OLDER DECISION HISTORY",
    )
    assert client.prompts[0].index(
        "OLDER DECISION HISTORY",
    ) < client.prompts[0].index("LATEST READY DECISION")
    assert client.prompts[0].index(
        "LATEST READY DECISION",
    ) < client.prompts[0].index("EXISTING MEMORY")


def test_conversations_remain_isolated_during_evolution() -> None:
    service = DecisionMemoryService(DecisionMemoryStore())
    ids_a = [save_record("evolution-main", f"A {index}") for index in range(2)]
    ids_b = [save_record("evolution-other", f"B {index}") for index in range(2)]
    memory_a = service.save_candidate(
        "evolution-main",
        memory_candidate(ids_a, "用户偏好较短通勤。"),
    )
    memory_b = service.save_candidate(
        "evolution-other",
        memory_candidate(ids_b, "用户偏好较低租金。"),
    )

    service.evolve_candidates(
        "evolution-main",
        [
            MemoryEvolutionCandidate(
                memory_id=memory_a.id,
                category=memory_a.category,
                content="用户持续偏好较短通勤。",
                confidence=0.9,
                evidence_record_ids=[UUID(record_id) for record_id in ids_a],
            ),
        ],
    )

    assert service.get_memory("evolution-other", memory_b.id) == memory_b


def test_store_failure_preserves_original_memory() -> None:
    store = FailingReplaceStore()
    service = DecisionMemoryService(store)
    record_ids = [
        save_record("evolution-failure", f"Decision {index}") for index in range(2)
    ]
    existing = service.save_candidate(
        "evolution-failure",
        memory_candidate(record_ids, "用户偏好较短通勤。"),
    )

    with pytest.raises(RuntimeError, match="store unavailable"):
        service.evolve_candidates(
            "evolution-failure",
            [
                MemoryEvolutionCandidate(
                    memory_id=existing.id,
                    category=existing.category,
                    content="用户现在偏好较低租金。",
                    confidence=0.9,
                    evidence_record_ids=[UUID(record_id) for record_id in record_ids],
                ),
            ],
        )

    assert service.list_memories("evolution-failure") == [existing]
