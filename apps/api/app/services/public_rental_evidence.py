from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urlparse
from xml.etree import ElementTree

import httpx


@dataclass(frozen=True)
class PublicRentalEvidence:
    source_reference: str
    source_title: str
    source_provider: str
    property_text: str
    observed_at: str
    published_at: str | None = None


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

    search_endpoint = "https://www.bing.com/search"

    def search(
        self,
        *,
        property_name: str,
        city: str | None,
        district: str | None,
        lng: float | None,
        lat: float | None,
    ) -> list[PublicRentalEvidence]:
        del lng, lat  # Grounded context is exposed to the model, not used as invented evidence.
        query = " ".join(
            part for part in (city, district, property_name, "租房", "租金") if part
        )
        try:
            response = httpx.get(
                self.search_endpoint,
                params={"q": query, "format": "rss", "count": "6"},
                headers={"User-Agent": "LiveOS/0.1 public-evidence"},
                timeout=10,
            )
            response.raise_for_status()
            root = ElementTree.fromstring(response.text)
        except (httpx.HTTPError, ElementTree.ParseError, ValueError):
            return []

        evidence: list[PublicRentalEvidence] = []
        for item in root.findall(".//item")[:6]:
            source_reference = (item.findtext("link") or "").strip()
            source_title = (item.findtext("title") or "").strip()
            published_at = (item.findtext("pubDate") or "").strip() or None
            if not source_reference or not _public_http_url(source_reference):
                continue
            page = self._read_source(source_reference, property_name)
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
                published_at=published_at,
            ))
            if len(evidence) == 3:
                break
        return evidence

    @staticmethod
    def _read_source(url: str, property_name: str) -> tuple[str, str] | None:
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": "LiveOS/0.1 public-evidence"},
                timeout=10,
                follow_redirects=False,
            )
            response.raise_for_status()
        except httpx.HTTPError:
            return None
        if "text/html" not in response.headers.get("content-type", "text/html"):
            return None
        parser = _VisibleTextParser()
        parser.feed(response.text[:1_000_000])
        text = " ".join(" ".join(parser.parts).split())
        needle = _normalized(property_name)
        normalized_text = _normalized(text)
        if not needle or needle not in normalized_text:
            return None
        index = normalized_text.find(needle)
        # Keep a bounded source excerpt while retaining enough surrounding rent evidence.
        start = max(0, index - 1500)
        excerpt = text[start:start + 6000]
        if not re.search(r"(?:租|月租|房租|元/月|每月|/月)", excerpt):
            return None
        return excerpt, datetime.now(UTC).isoformat()

    @staticmethod
    def as_tool_result(evidence: list[PublicRentalEvidence]) -> str:
        return __import__("json").dumps(
            {"evidence": [asdict(item) for item in evidence]},
            ensure_ascii=False,
        )


public_rental_evidence_search = PublicRentalEvidenceSearch()
