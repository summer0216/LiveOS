import json
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.ownership import COOKIE_NAME
from app.main import app
from app.stores.runtime import conversation_store


def test_attention_is_durable_turn_bound_and_not_exposed_as_a_client_side_grant():
    cid, other, owner = str(uuid4()), str(uuid4()), str(uuid4())
    conversation_store.get_or_create(cid, owner)
    conversation_store.get_or_create(other, owner)
    user_id = conversation_store.append(cid, "user", "这里附近有地铁吗？")
    assistant_id = conversation_store.append(cid, "assistant", "回复")
    other_id = conversation_store.append(other, "user", "另一个会话")
    snapshot = {"attention": {"conversation_id": cid, "source_user_turn_id": user_id}, "environment_ids": []}
    conversation_store.record_environment_attention(cid, user_id, snapshot)
    conversation_store.record_environment_attention(cid, assistant_id, snapshot)
    conversation_store.record_environment_attention(cid, other_id, snapshot)
    messages = conversation_store.get(cid).get_messages()
    assert messages[0].environment_attention == snapshot
    assert messages[1].environment_attention is None
    assert conversation_store.get(other).get_messages()[0].environment_attention is None
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, owner)
    first = client.get(f"/api/conversations/{cid}")
    assert first.status_code == 200
    assert first.json()["environment_eligibility"]["items"] == []  # Incomplete attention is not eligibility.
    assert "environment_attention" not in first.json()["messages"][0]
    assert client.get(f"/api/conversations/{cid}").json() == first.json()
    assert TestClient(app).get(f"/api/conversations/{cid}").status_code == 404
    conversation_store.append(cid, "user", "换个话题")
    assert client.get(f"/api/conversations/{cid}").json()["environment_eligibility"]["items"] == []


def test_history_rebuilds_three_tram_qualifications_from_durable_attention_and_current_evidence(monkeypatch):
    from dataclasses import asdict
    from datetime import UTC, datetime

    import httpx

    from app.models.environment_eligibility import EnvironmentEligibilityResult
    from app.models.property import GeographicPrecision, GeographicStatus, Property
    from app.services.environment_eligibility import (
        eligible_environment,
        environment_attention_snapshot,
    )
    from app.services.place_context_reality import PlaceContextRealityService, PlacePoi
    from app.stores.runtime import property_store

    def unexpected_network(*args, **kwargs):
        raise AssertionError("Resume must not query Provider or Model")

    monkeypatch.setattr(httpx, "get", unexpected_network)
    monkeypatch.setattr(httpx, "post", unexpected_network)
    cid, owner, pid = str(uuid4()), str(uuid4()), str(uuid4())
    conversation_store.get_or_create(cid, owner)
    client = TestClient(app)
    client.cookies.set(COOKIE_NAME, owner)
    assert client.get(f"/api/conversations/{cid}").json()["environment_eligibility"] is None
    home = property_store.create(Property(
        id=pid, conversation_id=cid, title="测试住所", geographic_identity="已确认测试住所",
        geographic_precision=GeographicPrecision.PLACE, geographic_status=GeographicStatus.GROUNDED,
        lng=116.4, lat=39.9,
    ))
    now = datetime.now(UTC).isoformat()
    context = [PlaceContextRealityService.admit(
        home=home, category="TRANSIT",
        place=PlacePoi(f"station-{i}", f"站点{i}", f"区域 站点{i}", code, 116.401, 39.901, 200, now),
        walking_minutes=None, walking_evidence=None, anchor_candidate=False,
    ) for i, code in enumerate(["150705"] * 3 + ["150700"] * 17)]
    home = property_store.update_place_context(pid, cid, context)
    user_id = conversation_store.append(cid, "user", "这里附近有地铁吗？")
    history = conversation_store.get(cid).get_messages()
    items = eligible_environment(
        {"property_id": pid, "category": "TRANSIT", "type_codes": ["150500"],
         "quote": "这里附近有地铁吗？", "environment_ids": []},
        conversation_id=cid, history=history, user_text=history[-1].content,
        properties=[home], focused_property_id=pid, attention_property_id=None,
    )
    result = EnvironmentEligibilityResult(cid, user_id, items)
    assert len(items) == 3
    conversation_store.record_environment_attention(cid, user_id, environment_attention_snapshot(result))
    conversation_store.append(cid, "assistant", "测试回复")
    first = client.get(f"/api/conversations/{cid}").json()
    expected = json.loads(json.dumps(asdict(result)))
    assert first["environment_eligibility"] == expected
    assert client.get(f"/api/conversations/{cid}").json() == first
    # Changed evidence is checked at resume, rather than reviving the prior grant.
    context[0]["admission"]["status"] = "REJECTED"
    property_store.update_place_context(pid, cid, context)
    refreshed = client.get(f"/api/conversations/{cid}").json()["environment_eligibility"]
    assert len(refreshed["items"]) == 2
    assert all(item["environment_type_code"] == "150705" for item in refreshed["items"])
    conversation_store.append(cid, "user", "谢谢，换个话题")
    assert client.get(f"/api/conversations/{cid}").json()["environment_eligibility"]["items"] == []
