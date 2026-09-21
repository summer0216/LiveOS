import json
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.ai_client import AIClient
from app.main import app
from app.models.property import (
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
    PropertyRentSource,
)
from app.services.external_rent_reality_service import ExternalRentRealityService
from app.services.property_manager import property_manager
from app.services.public_rental_evidence import PublicRentalEvidence
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


class FakePublicSearch:
    evidence = PublicRentalEvidence(
        source_reference="https://rent.example/listing/123",
        source_title="中关村东大院整租",
        source_provider="rent.example",
        property_text="中关村东大院 当前整租 6800 元/月",
        observed_at="2026-09-20T10:00:00+00:00",
        published_at="2026-09-20T09:00:00+00:00",
    )

    def search(self, **_kwargs):
        return [self.evidence]

    def as_tool_result(self, evidence):
        return json.dumps({"evidence": [item.__dict__ for item in evidence]}, ensure_ascii=False)


class FakeCompletions:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            function = SimpleNamespace(
                name="search_public_rental_evidence",
                arguments=json.dumps({
                    "property_name": "中关村东大院",
                    "city": "北京市",
                    "district": "北京市海淀区中关村东大院",
                    "lng": 116.32,
                    "lat": 39.98,
                }),
            )
            message = SimpleNamespace(
                content=None,
                tool_calls=[SimpleNamespace(id="call-1", function=function)],
            )
        else:
            tool_result = json.loads(kwargs["messages"][-1]["content"])
            evidence = tool_result["evidence"][0]
            message = SimpleNamespace(
                content=json.dumps({
                    "rent_monthly": 6800,
                    "identity_status": "GROUNDED",
                    "source_reference": evidence["source_reference"],
                    "observed_at": evidence["observed_at"],
                    "evidence_excerpt": "中关村东大院 当前整租 6800 元/月",
                }),
                tool_calls=None,
            )
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class FakeOpenAI:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions())

    def with_options(self, **_kwargs):
        return self


def test_model_tool_evidence_becomes_guarded_external_rent_reality():
    client = TestClient(app)
    conversation_id = uuid_for("external-rent-reality")
    create_owned_conversation(client, conversation_id)
    target = property_manager.create(conversation_id, Property(
        title="中关村东大院",
        district="北京市",
        geographic_identity="北京市海淀区中关村东大院",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.32,
        lat=39.98,
        provenance=PropertyProvenance.AMAP_RESIDENTIAL_POI,
        external_id="amap-home-1",
    ))
    intelligence = AIClient()
    fake_openai = FakeOpenAI()
    intelligence.client = fake_openai
    service = ExternalRentRealityService(
        intelligence=intelligence,
        evidence_search=FakePublicSearch(),
    )

    result = service.acquire(conversation_id, target.id or "")

    assert result.status == "UPDATED"
    stored = property_manager.get_scoped(target.id or "", conversation_id)
    assert stored is not None
    assert stored.rent == 6800
    assert stored.rent_source == PropertyRentSource.EXTERNAL_SOURCE
    assert stored.rent_source_reference == "https://rent.example/listing/123"
    assert stored.rent_observed_at == "2026-09-20T10:00:00+00:00"
    calls = fake_openai.chat.completions.calls
    assert calls[0]["tools"][0]["function"]["name"] == "search_public_rental_evidence"
    assert calls[1]["messages"][-1]["role"] == "tool"


def test_public_evidence_action_stops_before_reality_admission():
    client = TestClient(app)
    conversation_id = uuid_for("public-evidence-action")
    create_owned_conversation(client, conversation_id)
    target = property_manager.create(conversation_id, Property(
        title="中关村东大院",
        geographic_identity="北京市海淀区中关村东大院",
        geographic_status=GeographicStatus.GROUNDED,
        lng=116.32,
        lat=39.98,
        meaningful_unknown="中关村东大院的月租金是多少？",
        meaningful_unknown_why="租金会改变当前预算权衡。",
        reality_action_type="PUBLIC_EVIDENCE",
        reality_action_label="查询公开租金挂牌信息",
        reality_action_why="公开挂牌可提供来源",
        reality_action_state_hash="action-state-1",
    ))
    intelligence = AIClient()
    fake_openai = FakeOpenAI()
    intelligence.client = fake_openai
    service = ExternalRentRealityService(
        intelligence=intelligence, evidence_search=FakePublicSearch(),
    )

    before = property_manager.get_scoped(target.id or "", conversation_id)
    assert before is not None and before.public_rent_evidence is None
    result = service.execute_public_evidence_action(conversation_id, target.id or "")
    assert result.status == "EVIDENCE_READY"
    stored = property_manager.get_scoped(target.id or "", conversation_id)
    assert stored is not None and stored.public_rent_evidence is not None
    assert stored.public_rent_evidence["source_reference"] == "https://rent.example/listing/123"
    assert stored.public_rent_evidence["observed_at"] == "2026-09-20T10:00:00+00:00"
    assert stored.rent is None and stored.rent_source is None
    assert stored.meaningful_unknown == before.meaningful_unknown
    assert stored.current_judgment == before.current_judgment
    assert fake_openai.chat.completions.calls[0]["tools"][0]["function"]["name"] == "search_public_rental_evidence"
