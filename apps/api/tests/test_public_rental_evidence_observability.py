import json

from app.core import external_rent_observability
from app.services import public_rental_evidence as evidence_module


class _Response:
    def __init__(self, text="", *, content_type="text/html", payload=None):
        self.text = text
        self.status_code = 200
        self.headers = {"content-type": content_type}
        self._payload = payload
        self.url = "https://rent.example/listing/1"

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_observability_does_not_change_public_rental_search_semantics(monkeypatch, tmp_path):
    monkeypatch.setattr(external_rent_observability.settings, "APP_ENV", "development")
    monkeypatch.setattr(
        external_rent_observability, "TRACE_PATH", tmp_path / "external-rent.jsonl",
    )
    monkeypatch.setattr(evidence_module, "_public_http_url", lambda _url: True)
    def fake_post(url, **_kwargs):
        assert url == evidence_module.PublicRentalEvidenceSearch.search_endpoint
        return _Response(payload={
            "content": [
                {"type": "server_tool_use", "name": "web_search"},
                {
                    "type": "web_search_tool_result",
                    "content": [{
                        "type": "web_search_result",
                        "title": "Rent listing",
                        "url": "https://rent.example/listing/1",
                    }],
                },
                {
                    "type": "text",
                    "text": "Generated prose https://prose.example/must-not-be-used",
                },
            ],
        })

    def fake_get(url, **_kwargs):
        assert url == "https://rent.example/listing/1"
        return _Response(
            "<html><body>北京市海淀区融科昆仑巢，整租月租 6800 元/月</body></html>",
            content_type="text/html; charset=utf-8",
        )

    monkeypatch.setattr(evidence_module.httpx, "post", fake_post)
    monkeypatch.setattr(evidence_module.httpx, "get", fake_get)
    search = evidence_module.PublicRentalEvidenceSearch()
    args = {
        "property_name": "融科昆仑巢",
        "property_identity": "北京市海淀区融科昆仑巢",
        "city": "北京市",
        "district": "北京市海淀区",
        "lng": 116.3,
        "lat": 39.9,
    }

    plain = search.search(**args)
    traced = search.search(**args, trace_id="test-execution")

    assert len(plain) == len(traced) == 1
    assert {
        key: getattr(plain[0], key)
        for key in ("source_reference", "source_title", "source_provider", "property_text", "published_at")
    } == {
        key: getattr(traced[0], key)
        for key in ("source_reference", "source_title", "source_provider", "property_text", "published_at")
    }
    assert plain[0].observed_at and traced[0].observed_at
    assert plain[0].grounded_property_identity == "北京市海淀区融科昆仑巢"

    events = [
        json.loads(line)
        for line in (tmp_path / "external-rent.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [event["event"] for event in events] == [
        "search_request",
        "search_response",
        "search_parse",
        "candidate_url_accepted",
        "candidate_page_read",
        "search_complete",
    ]
    assert events[0]["query"] == "北京市 北京市海淀区 融科昆仑巢 租房 租金"
    assert events[2]["native_search_executed"] is True
    assert events[2]["search_result_count"] == 1
    assert events[-1]["public_rental_evidence_count"] == 1
    assert events[-1]["extracted_candidate_rent_evidence_count"] == 1
    candidate = events[3]
    assert candidate["search_title"] == "Rent listing"
    assert candidate["candidate_url"] == "https://rent.example/listing/1"
    assert candidate["candidate_domain"] == "rent.example"
    assert candidate["property_in_search_title"] is False
    assert candidate["property_in_url"] is False
    page_read = events[4]
    assert page_read["fetch_success"] is True
    assert page_read["property_in_raw_page"] is True
    assert page_read["property_in_visible_text"] is True
    assert page_read["raw_identity_sample"]
    assert len(page_read["raw_identity_sample"]) <= 240
    assert page_read["success"] is True


def test_public_rental_search_rejects_same_name_without_grounded_location(monkeypatch):
    monkeypatch.setattr(evidence_module, "_public_http_url", lambda _url: True)

    def fake_post(url, **_kwargs):
        assert url == evidence_module.PublicRentalEvidenceSearch.search_endpoint
        return _Response(payload={
            "content": [{
                "type": "web_search_tool_result",
                "content": [{
                    "type": "web_search_result",
                    "title": "融科昆仑巢整租",
                    "url": "https://rent.example/listing/1",
                }],
            }],
        })

    def fake_get(url, **_kwargs):
        assert url == "https://rent.example/listing/1"
        return _Response(
            "<html><body>融科昆仑巢，整租月租 6800 元/月</body></html>",
            content_type="text/html; charset=utf-8",
        )

    monkeypatch.setattr(evidence_module.httpx, "post", fake_post)
    monkeypatch.setattr(evidence_module.httpx, "get", fake_get)

    evidence = evidence_module.PublicRentalEvidenceSearch().search(
        property_name="融科昆仑巢",
        property_identity="北京市海淀区融科昆仑巢",
        city="北京市",
        district="北京市海淀区",
        lng=116.3,
        lat=39.9,
    )

    assert evidence == []
