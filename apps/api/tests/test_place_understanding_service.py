import json
from datetime import UTC, datetime

from app.main import app
from app.models.property import (
    GeographicPrecision,
    GeographicStatus,
    Property,
    PropertyProvenance,
)
from app.models.reality_evidence import RealityAdmission, RealityEvidence
from app.schemas.property import PropertyResponse
from app.services.place_understanding_service import PlaceUnderstandingService
from app.services.property_manager import property_manager
from app.services.transit_duration import TransitDurationService
from fastapi.testclient import TestClient
from tests.ids import uuid_for
from tests.ownership import create_owned_conversation


def test_grounded_place_context_admits_only_supported_place_understanding():
    class Intelligence:
        def __init__(self, supported: bool):
            self.supported = supported
            self.prompts = []

        def generate_json(self, prompt, **_kwargs):
            self.prompts.append(prompt)
            if len(self.prompts) % 2:
                return json.dumps({
                    "claims": [{
                        "text": (
                            "住宅周边的教育与商业功能在同一片区域共存"
                            if self.supported else "大学带动了区域发展，配套完善"
                        ),
                        "evidence_ids": ["university", "mall"],
                    }],
                    "anchor_ids": ["university"],
                })
            return json.dumps({
                "supported": self.supported,
                "unsupported_claims": [] if self.supported else ["大学带动了区域发展，配套完善"],
                "place_pattern": self.supported,
            })

    client = TestClient(app)
    conversation_id = uuid_for("place-understanding")
    create_owned_conversation(client, conversation_id)
    def home(title):
        created = property_manager.create(conversation_id, Property(
            title=title, geographic_identity=title,
            geographic_precision=GeographicPrecision.COMMUNITY,
            geographic_status=GeographicStatus.GROUNDED,
            lng=104.074, lat=30.668,
            provenance=PropertyProvenance.USER_PROVIDED,
        ))
        observed_at = datetime.now(UTC).isoformat()
        context = []
        for category, external_id, name, type_code, lng, lat, distance, minutes, anchor in [
            ("EDUCATION", "university", "真实大学", "141201", 104.075, 30.669, 180, 3, True),
            ("COMMERCIAL", "mall", "真实购物中心", "060101", 104.077, 30.670, 350, 5, True),
        ]:
            identity = f"真实地点 {name}"
            evidence = RealityEvidence(
                source_provider="AMAP",
                source_reference="https://restapi.amap.com/v3/place/around",
                source_record_id=external_id,
                identity=identity,
                observed_at=observed_at,
            )
            walking_evidence = RealityEvidence(
                source_provider="AMAP",
                source_reference=TransitDurationService.walking_endpoint,
                source_record_id=f"{created.id}:{external_id}:walking",
                identity=f"{created.geographic_identity} -> {identity}",
                observed_at=observed_at,
            )
            admission = RealityAdmission.admit(
                evidence,
                property_id=created.id or "",
                property_identity=created.geographic_identity or "",
                property_lng=created.lng or 0,
                property_lat=created.lat or 0,
                authority="PLACE_CONTEXT_REALITY_ADMISSION",
            )
            assert admission is not None
            walking_admission = RealityAdmission.admit(
                walking_evidence,
                property_id=created.id or "",
                property_identity=created.geographic_identity or "",
                property_lng=created.lng or 0,
                property_lat=created.lat or 0,
                authority="PLACE_CONTEXT_WALKING_TIME_ADMISSION",
            )
            assert walking_admission is not None
            context.append({
                "structure_version": 3, "category": category,
                "external_id": external_id, "name": name,
                "identity": identity, "type_code": type_code,
                "lng": lng, "lat": lat, "distance_m": distance,
                "walking_minutes": minutes, "anchor_candidate": anchor,
                "co_located_with": [], "evidence": evidence.to_dict(),
                "admission": admission.to_dict(),
                "walking_evidence": walking_evidence.to_dict(),
                "walking_admission": walking_admission.to_dict(),
            })
        return property_manager.update_place_context(
            created.id or "", conversation_id, context,
        )

    valid = home("已核实住宅甲")
    assert valid is not None
    intelligence = Intelligence(True)
    result = PlaceUnderstandingService(intelligence=intelligence).form(
        conversation_id, valid.id or "",
    )
    assert result.status == "UPDATED"
    assert "真实大学" in intelligence.prompts[0]
    assert "真实购物中心" in intelligence.prompts[0]
    assert "rent" not in intelligence.prompts[0].lower()
    stored = property_manager.get_scoped(valid.id or "", conversation_id)
    assert stored is not None
    assert PropertyResponse.model_validate(stored).place_understanding is not None
    assert stored.place_understanding["claims"][0]["evidence_ids"] == ["university", "mall"]
    assert "教育与商业功能" in stored.place_understanding["claims"][0]["text"]
    assert stored.living_meaning is None and stored.current_judgment is None

    unsupported = home("已核实住宅乙")
    assert unsupported is not None
    rejected = PlaceUnderstandingService(intelligence=Intelligence(False)).form(
        conversation_id, unsupported.id or "",
    )
    assert rejected.status == "REJECTED"
    assert property_manager.get_scoped(unsupported.id or "", conversation_id).place_understanding is None

    class RetryIntelligence:
        calls = 0

        def generate_json(self, prompt, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return json.dumps({
                    "claims": [{"text": "教育与商业功能在周边共存", "evidence_ids": ["university", "mall"]}],
                    "anchor_ids": ["university", "mall", "invented"],
                })
            if self.calls == 2:
                return json.dumps({
                    "claims": [{"text": "教育与商业功能在周边共存", "evidence_ids": ["university", "mall"]}],
                    "anchor_ids": ["university", "mall"],
                })
            return json.dumps({"supported": True, "unsupported_claims": [], "place_pattern": True})

    retry_home = home("已核实住宅丙")
    assert retry_home is not None
    retry_intelligence = RetryIntelligence()
    retry_result = PlaceUnderstandingService(intelligence=retry_intelligence).form(
        conversation_id, retry_home.id or "",
    )
    assert retry_result.status == "UPDATED"
    assert retry_intelligence.calls == 3
    response = client.get(f"/api/properties?conversation_id={conversation_id}")
    assert response.status_code == 200
    returned = next(item for item in response.json()["items"] if item["id"] == retry_home.id)
    assert returned["place_understanding"]["claims"][0]["text"] == "教育与商业功能在周边共存"

    class SummaryOnlyIntelligence:
        calls = 0

        def generate_json(self, _prompt, **_kwargs):
            self.calls += 1
            if self.calls % 2:
                return json.dumps({
                    "claims": [{"text": "大学和购物中心都在附近", "evidence_ids": ["university", "mall"]}],
                    "anchor_ids": [],
                })
            return json.dumps({"supported": True, "unsupported_claims": [], "place_pattern": False})

    summary_home = home("已核实住宅丁")
    assert summary_home is not None
    summary_result = PlaceUnderstandingService(intelligence=SummaryOnlyIntelligence()).form(
        conversation_id, summary_home.id or "",
    )
    assert summary_result.status == "REJECTED"
    assert property_manager.get_scoped(summary_home.id or "", conversation_id).place_understanding is None

    class ModelIntelligence:
        def __init__(self, supported):
            self.supported = supported
            self.calls = 0

        def generate_json(self, _prompt, **_kwargs):
            self.calls += 1
            if self.calls == 1:
                return json.dumps({
                    "claims": [
                        {"text": "教育与商业功能在住宅周边共存", "evidence_ids": ["university", "mall"]},
                        {"text": "大学与购物中心处于同一周边范围", "evidence_ids": ["university", "mall"]},
                    ],
                    "anchor_ids": ["university", "mall"],
                })
            if self.calls == 2:
                return json.dumps({"supported": True, "unsupported_claims": [], "place_pattern": True})
            if self.calls % 2:
                return json.dumps({
                    "text": (
                        "这片区域因大学而发展成成熟宜居社区"
                        if not self.supported else
                        "住宅周边的大学与购物中心构成教育和商业功能共存的地方环境"
                    ),
                    "pattern_indices": [0, 1],
                    "evidence_ids": ["university", "mall"],
                })
            return json.dumps({
                "supported": self.supported,
                "unsupported_claims": [] if self.supported else ["因大学而发展成成熟宜居社区"],
                "coherent_model": self.supported,
            })

    model_home = home("已核实住宅戊")
    assert model_home is not None
    model_result = PlaceUnderstandingService(intelligence=ModelIntelligence(True)).form(
        conversation_id, model_home.id or "",
    )
    assert model_result.status == "UPDATED"
    model_stored = property_manager.get_scoped(model_home.id or "", conversation_id)
    assert model_stored is not None
    assert model_stored.place_understanding["place_model"]["pattern_indices"] == [0, 1]
    assert "教育和商业功能共存" in model_stored.place_understanding["place_model"]["text"]
    assert PropertyResponse.model_validate(model_stored).place_understanding["place_model"]

    causal_home = home("已核实住宅己")
    assert causal_home is not None
    causal_result = PlaceUnderstandingService(intelligence=ModelIntelligence(False)).form(
        conversation_id, causal_home.id or "",
    )
    assert causal_result.status == "REJECTED"
    assert property_manager.get_scoped(causal_home.id or "", conversation_id).place_understanding is None


def test_legacy_context_cannot_form_or_retain_place_understanding():
    client = TestClient(app)
    conversation_id = uuid_for("place-understanding-legacy")
    create_owned_conversation(client, conversation_id)
    home = property_manager.create(conversation_id, Property(
        title="旧版上下文住所", geographic_identity="旧版上下文住所",
        geographic_precision=GeographicPrecision.COMMUNITY,
        geographic_status=GeographicStatus.GROUNDED,
        lng=104.074, lat=30.668,
        provenance=PropertyProvenance.USER_PROVIDED,
    ))
    legacy_context = [{
        "structure_version": 2, "category": "EDUCATION",
        "external_id": "legacy-poi", "name": "旧地点",
        "identity": "旧地点 identity", "type_code": "141201",
        "lng": 104.075, "lat": 30.669, "distance_m": 180,
        "walking_minutes": 3, "anchor_candidate": True,
        "co_located_with": [],
    }]
    property_manager.update_place_context(
        home.id or "", conversation_id, legacy_context,
    )
    property_manager.update_place_understanding(
        home.id or "", conversation_id,
        {"claims": [{"text": "旧理解", "evidence_ids": ["legacy-poi"]}],
         "anchor_ids": [], "reality_hash": "legacy"},
    )

    restored = property_manager.get_scoped(home.id or "", conversation_id)
    assert restored is not None
    assert restored.place_context == legacy_context
    assert restored.place_understanding is None

    class NeverCalled:
        def generate_json(self, *_args, **_kwargs):
            raise AssertionError("unadmitted legacy context reached understanding")

    result = PlaceUnderstandingService(intelligence=NeverCalled()).form(
        conversation_id, home.id or "",
    )
    assert result.status == "INSUFFICIENT_REALITY"

    unqualified_v3 = [
        {**legacy_context[0], "structure_version": 3},
    ]
    property_manager.update_place_context(
        home.id or "", conversation_id, unqualified_v3,
    )
    rejected = PlaceUnderstandingService(intelligence=NeverCalled()).form(
        conversation_id, home.id or "",
    )
    assert rejected.status == "INSUFFICIENT_REALITY"
