from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse

import httpx
from app.core.config import settings
from app.core.external_rent_observability import record_external_rent_search_trace
from app.models.reality_evidence import RealityEvidence


@dataclass(frozen=True)
class PublicRentalEvidence:
    source_reference: str
    source_title: str
    source_provider: str
    property_text: str
    observed_at: str
    published_at: str | None = None
    grounded_property_identity: str | None = None

    def reality_evidence(self) -> RealityEvidence:
        return RealityEvidence(
            source_provider=self.source_provider,
            source_reference=self.source_reference,
            identity=self.grounded_property_identity or "",
            observed_at=self.observed_at,
        )


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._hidden:
            self._hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden and data.strip():
            self.parts.append(data.strip())


def _normalized(value: str) -> str:
    return re.sub(r"[\s，,。.!！?？、·—_\-（）()]", "", value).casefold()


def _bounded(value: str | None, limit: int) -> str:
    return (value or "")[:limit]


def _identity_is_grounded(
    text: str, *, property_name: str, property_identity: str,
) -> bool:
    normalized_text = _normalized(text)
    normalized_name = _normalized(property_name)
    normalized_identity = _normalized(property_identity)
    if (
        not normalized_name
        or not normalized_identity
        or normalized_name not in normalized_text
    ):
        return False

    administrative_parts = re.findall(
        r"[^省市区县]+(?:省|市|区|县)", property_identity,
    )
    if len(administrative_parts) >= 2 and administrative_parts[0].endswith("省"):
        administrative_parts = administrative_parts[1:]
    location_parts = [_normalized(part) for part in administrative_parts]
    for match in re.finditer(re.escape(normalized_name), normalized_text):
        start = max(0, match.start() - 400)
        end = min(len(normalized_text), match.end() + 400)
        identity_context = normalized_text[start:end]
        if location_parts:
            if all(part in identity_context for part in location_parts):
                return True
        elif normalized_identity in identity_context:
            return True
    return False


def _identity_diagnostic(text: str, property_name: str) -> tuple[str | None, str]:
    """Return a bounded sample around an exact or partial name match for dev tracing."""
    normalized_name = _normalized(property_name)
    normalized_text = _normalized(text)
    if not normalized_name:
        return None, ""
    match = normalized_name if normalized_name in normalized_text else None
    if match is None:
        for size in range(len(normalized_name) - 1, 1, -1):
            match = next((normalized_name[i:i + size]
                          for i in range(len(normalized_name) - size + 1)
                          if normalized_name[i:i + size] in normalized_text), None)
            if match:
                break
    if not match:
        return None, ""
    raw_index = text.casefold().find(match.casefold())
    if raw_index < 0:
        return match, _bounded(text, 240)
    start = max(0, raw_index - 100)
    return match, _bounded(text[start:raw_index + len(match) + 100], 240)


def _public_http_url(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except socket.gaierror:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            return False
    return True


class PublicRentalEvidenceSearch:
    """Read a few traceable public pages returned by a public web index."""

    search_endpoint = "https://api.deepseek.com/anthropic/v1/messages"

    def search(
        self,
        *,
        property_name: str,
        property_identity: str,
        city: str | None,
        district: str | None,
        lng: float | None,
        lat: float | None,
        trace_id: str | None = None,
    ) -> list[PublicRentalEvidence]:
        del lng, lat  # Grounded context is exposed to the model, not used as invented evidence.
        query = " ".join(
            part for part in (city, district, property_name, "租房", "租金") if part
        )
        if trace_id:
            record_external_rent_search_trace(
                trace_id, "search_request", attempted=True, query=query,
            )
        try:
            response = httpx.post(
                self.search_endpoint,
                headers={
                    "x-api-key": settings.OPENAI_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": settings.OPENAI_MODEL,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": query}],
                    "tools": [{
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": 1,
                    }],
                },
                timeout=120,
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise TypeError("DeepSeek search returned a non-object response.")
            if trace_id:
                record_external_rent_search_trace(
                    trace_id, "search_response", status_code=response.status_code,
                )
        except (httpx.HTTPError, json.JSONDecodeError, TypeError, ValueError) as exc:
            if trace_id:
                record_external_rent_search_trace(
                    trace_id, "search_failure",
                    failure_type=type(exc).__name__,
                    status_code=getattr(getattr(exc, "response", None), "status_code", None),
                )
            return []

        search_results: list[dict[str, str]] = []
        seen_urls: set[str] = set()
        native_search_executed = False
        for block in payload.get("content", []):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "server_tool_use" and block.get("name") == "web_search":
                native_search_executed = True
                continue
            if block.get("type") != "web_search_tool_result":
                continue
            native_search_executed = True
            content = block.get("content")
            if not isinstance(content, list):
                continue
            for result in content:
                if not isinstance(result, dict) or result.get("type") != "web_search_result":
                    continue
                source_reference = result.get("url")
                if not isinstance(source_reference, str):
                    continue
                source_reference = source_reference.strip()
                if not source_reference or source_reference in seen_urls:
                    continue
                source_title = result.get("title")
                search_results.append({
                    "url": source_reference,
                    "title": source_title.strip() if isinstance(source_title, str) else "",
                })
                seen_urls.add(source_reference)

        evidence: list[PublicRentalEvidence] = []
        candidates = search_results[:6]
        candidate_url_count = len(candidates)
        if trace_id:
            record_external_rent_search_trace(
                trace_id, "search_parse",
                native_search_executed=native_search_executed,
                search_result_count=len(search_results),
                candidate_count=len(candidates),
                candidate_url_count=candidate_url_count,
            )
        for candidate_index, candidate in enumerate(candidates, start=1):
            source_reference = candidate["url"]
            source_title = candidate["title"]
            parsed_url = urlparse(source_reference)
            decoded_url = unquote(source_reference)
            normalized_name = _normalized(property_name)
            candidate_trace = {
                "candidate_index": candidate_index,
                "search_title": _bounded(source_title, 240),
                "candidate_url": _bounded(source_reference, 600),
                "candidate_domain": _bounded(parsed_url.hostname, 180),
                "property_in_search_title": bool(normalized_name and normalized_name in _normalized(source_title)),
                "property_in_url": bool(normalized_name and normalized_name in _normalized(decoded_url)),
            }
            if not _public_http_url(source_reference):
                if trace_id:
                    record_external_rent_search_trace(
                        trace_id, "candidate_rejected",
                        **candidate_trace, reason="not_public_http_url",
                    )
                continue
            if trace_id:
                record_external_rent_search_trace(
                    trace_id, "candidate_url_accepted", **candidate_trace,
                )
            page = self._read_source(
                source_reference, property_name, property_identity,
                trace_id=trace_id,
                candidate_index=candidate_index,
                candidate_trace=candidate_trace,
            )
            if page is None:
                continue
            page_text, observed_at = page
            provider = urlparse(source_reference).hostname or "public-web"
            evidence.append(PublicRentalEvidence(
                source_reference=source_reference,
                source_title=source_title or property_name,
                source_provider=provider,
                property_text=page_text,
                observed_at=observed_at,
                published_at=None,
                grounded_property_identity=property_identity,
            ))
            if len(evidence) == 3:
                break
        if trace_id:
            record_external_rent_search_trace(
                trace_id, "search_complete",
                candidate_count=len(candidates),
                candidate_url_count=candidate_url_count,
                extracted_candidate_rent_evidence_count=len(evidence),
                public_rental_evidence_count=len(evidence),
                rent_amount_extraction="not_performed_in_search",
            )
        return evidence

    @staticmethod
    def _read_source(
        url: str,
        property_name: str,
        property_identity: str,
        *,
        trace_id: str | None = None,
        candidate_index: int | None = None,
        candidate_trace: dict[str, object] | None = None,
    ) -> tuple[str, str] | None:
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": "LiveOS/0.1 public-evidence"},
                timeout=10,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            if trace_id:
                record_external_rent_search_trace(
                    trace_id, "candidate_page_read",
                    **(candidate_trace or {}),
                    success=False,
                    reason="http_error", failure_type=type(exc).__name__,
                    status_code=getattr(getattr(exc, "response", None), "status_code", None),
                    final_url=None,
                )
            return None
        if "text/html" not in response.headers.get("content-type", "text/html"):
            if trace_id:
                record_external_rent_search_trace(
                    trace_id, "candidate_page_read",
                    **(candidate_trace or {}),
                    success=False,
                    reason="non_html_content_type",
                    final_url=_bounded(str(getattr(response, "url", url)), 600),
                )
            return None
        parser = _VisibleTextParser()
        parser.feed(response.text[:1_000_000])
        text = " ".join(" ".join(parser.parts).split())
        needle = _normalized(property_name)
        normalized_text = _normalized(text)
        raw_match, raw_sample = _identity_diagnostic(response.text[:1_000_000], property_name)
        visible_match, visible_sample = _identity_diagnostic(text, property_name)
        identity_trace = {
            **(candidate_trace or {}),
            "candidate_index": candidate_index,
            "fetch_success": True,
            "http_status": response.status_code,
            "final_url": _bounded(str(getattr(response, "url", url)), 600),
            "property_in_raw_page": bool(needle and needle in _normalized(response.text[:1_000_000])),
            "property_in_visible_text": bool(needle and needle in normalized_text),
            "raw_identity_like_match": raw_match,
            "raw_identity_sample": raw_sample,
            "visible_identity_like_match": visible_match,
            "visible_identity_sample": visible_sample,
        }
        if not _identity_is_grounded(
            text,
            property_name=property_name,
            property_identity=property_identity,
        ):
            if trace_id:
                record_external_rent_search_trace(
                    trace_id, "candidate_page_read",
                    **identity_trace, success=False,
                    reason="grounded_property_identity_not_found",
                )
            return None
        index = normalized_text.find(needle)
        # Keep a bounded source excerpt while retaining enough surrounding rent evidence.
        start = max(0, index - 1500)
        excerpt = text[start:start + 6000]
        if not re.search(r"(?:租|月租|房租|元/月|每月|/月)", excerpt):
            if trace_id:
                record_external_rent_search_trace(
                    trace_id, "candidate_page_read",
                    **identity_trace, success=False,
                    reason="rent_text_not_found",
                )
            return None
        if trace_id:
            record_external_rent_search_trace(
                trace_id, "candidate_page_read",
                **identity_trace, success=True,
                excerpt_length=len(excerpt),
            )
        return excerpt, datetime.now(UTC).isoformat()

    @staticmethod
    def as_tool_result(evidence: list[PublicRentalEvidence]) -> str:
        return __import__("json").dumps(
            {"evidence": [asdict(item) for item in evidence]},
            ensure_ascii=False,
        )


public_rental_evidence_search = PublicRentalEvidenceSearch()
