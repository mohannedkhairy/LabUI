"""Public metadata APIs. Dates and abstracts are supplied by each source.

See docs/PUBLICATION_SCOUT.md for API references and coverage limits.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from html import unescape
from urllib.parse import quote, unquote, urlsplit

import httpx

TERMS = ("nanobubble", "nano bubbles", "ultrafine bubbles", "ultra fine bubbles")
TOPIC = re.compile(r"\b(?:nano[\s\-‐‑–]*bubbles?|ultra[\s\-‐‑–]*fine[\s-]+(?:gas[\s-]+)?bubbles?)\b", re.IGNORECASE)
PAGE_SIZE = 100
MAX_PAGES = 20


def plain(value) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", str(value or "")))).strip()


def safe_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if parsed.scheme in {"https", "http"} and parsed.hostname and not parsed.username and not parsed.password:
            return value
    except ValueError:
        pass
    return ""


def normalize_doi(value: str) -> str:
    value = unquote(value or "").strip().lower()
    value = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", value)
    return value if re.fullmatch(r"10\.\d{4,9}/\S+", value) else ""


def source_date(value: str) -> str:
    """Keep source precision; never manufacture a month or day."""
    value = (value or "")[:10]
    try:
        if len(value) == 10:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                return ""
            date.fromisoformat(value)
        elif len(value) == 7:
            date.fromisoformat(value + "-01")
        elif len(value) == 4:
            date.fromisoformat(value + "-01-01")
        else:
            return ""
        return value
    except ValueError:
        return ""


@dataclass
class Paper:
    source: str
    source_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    journal: str = ""
    published: str = ""
    doi: str = ""
    url: str = ""
    kind: str = "article"

    def relevant(self) -> bool:
        return bool(self.title and TOPIC.search(self.title + " " + self.abstract))


class SourceClient:
    def __init__(self, client: httpx.Client, heartbeat: Callable = lambda: None,
                 sleep: Callable = time.sleep):
        self.client, self.heartbeat, self.sleep = client, heartbeat, sleep

    def get(self, url, params):
        for attempt in range(3):
            self.heartbeat()
            try:
                response = self.client.get(url, params=params)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                    raise
                try:
                    wait = float(exc.response.headers.get("Retry-After", 2 ** attempt))
                except ValueError:
                    wait = 2 ** attempt
                # Long rate limits are retried by the persisted hourly retry.
                if wait > 30:
                    raise
                self.sleep(max(1, wait))
            except httpx.TransportError:
                if attempt == 2:
                    raise
                self.sleep(2 ** attempt)

    def crossref(self, since: date, until: date):
        for term in TERMS:
            cursor = "*"
            for _ in range(MAX_PAGES):
                message = self.get("https://api.crossref.org/works", {
                    "query": term, "rows": PAGE_SIZE, "cursor": cursor,
                    "filter": f"from-pub-date:{since},until-pub-date:{until}",
                }).json()["message"]
                items = message["items"]
                for item in items:
                    if item.get("type") not in {"journal-article", "proceedings-article", "posted-content", "book-chapter"}:
                        continue
                    published = ""
                    for key in ("published-online", "posted", "published", "published-print", "issued"):
                        parts = (item.get(key) or {}).get("date-parts") or []
                        if parts and parts[0]:
                            parts = parts[0]
                            value = "-".join([str(parts[0])] + [f"{v:02d}" for v in parts[1:3]])
                            if valid := source_date(value):
                                published = valid
                                break
                    doi = normalize_doi(item.get("DOI", ""))
                    yield Paper(
                        source="Crossref", source_id=doi, doi=doi,
                        title=plain((item.get("title") or [""])[0]),
                        authors=[plain(a.get("name") or " ".join(filter(None, [a.get("given"), a.get("family")])))
                                 for a in item.get("author", [])],
                        abstract=plain(item.get("abstract")),
                        journal=plain((item.get("container-title") or [""])[0]),
                        published=published,
                        url=f"https://doi.org/{quote(doi, safe='/')}" if doi else safe_url(item.get("URL", "")),
                        kind="preprint" if item.get("type") == "posted-content" else item.get("type", "article"),
                    )
                if len(items) < PAGE_SIZE:
                    break
                next_cursor = message.get("next-cursor")
                if not next_cursor or next_cursor == cursor:
                    raise RuntimeError("Crossref pagination stopped before all results were retrieved")
                cursor = next_cursor
                self.sleep(1)
            else:
                raise RuntimeError("Crossref page limit reached; coverage is incomplete")

    def europe_pmc(self, since: date, until: date):
        cursor = "*"
        query = '(nanobubble* OR "nano bubbles" OR "ultrafine bubbles" OR "ultra fine bubbles")'
        query += f" AND FIRST_PDATE:[{since} TO {until}]"
        fetched = 0
        for _ in range(MAX_PAGES):
            data = self.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", {
                "query": query, "format": "json", "resultType": "core",
                "pageSize": PAGE_SIZE, "cursorMark": cursor,
            }).json()
            items = data["resultList"]["result"]
            fetched += len(items)
            for item in items:
                doi = normalize_doi(item.get("doi", ""))
                journal = (item.get("journalInfo") or {}).get("journal") or {}
                source_id = f"{item['source']}/{item['id']}"
                yield Paper(
                    source="Europe PMC", source_id=source_id, doi=doi,
                    title=plain(item.get("title")), abstract=plain(item.get("abstractText")),
                    authors=[plain(a.get("fullName")) for a in (item.get("authorList") or {}).get("author", [])],
                    journal=plain(journal.get("title")),
                    published=source_date(item.get("firstPublicationDate", "")),
                    url=f"https://doi.org/{quote(doi, safe='/')}" if doi else f"https://europepmc.org/article/{quote(source_id, safe='/')}",
                    kind="preprint" if item.get("source") == "PPR" else "article",
                )
            if fetched >= int(data["hitCount"]):
                break
            next_cursor = data.get("nextCursorMark")
            if not items or not next_cursor or next_cursor == cursor:
                raise RuntimeError("Europe PMC pagination stopped before all results were retrieved")
            cursor = next_cursor
            self.sleep(1)
        else:
            raise RuntimeError("Europe PMC page limit reached; coverage is incomplete")

    def arxiv(self, since: date, until: date):
        ns = {"a": "http://www.w3.org/2005/Atom", "ar": "http://arxiv.org/schemas/atom",
              "os": "http://a9.com/-/spec/opensearch/1.1/"}
        query = '(all:nanobubble OR all:nanobubbles OR all:"nano bubbles" OR all:"ultrafine bubbles" OR all:"ultra fine bubbles")'
        query += f" AND submittedDate:[{since:%Y%m%d}0000 TO {until:%Y%m%d}2359]"
        for page in range(MAX_PAGES):
            feed = ET.fromstring(self.get("https://export.arxiv.org/api/query", {
                "search_query": query, "start": page * PAGE_SIZE, "max_results": PAGE_SIZE,
                "sortBy": "submittedDate", "sortOrder": "ascending",
            }).content)
            entries = feed.findall("a:entry", ns)
            total = int(feed.findtext("os:totalResults", namespaces=ns))
            for item in entries:
                url = item.findtext("a:id", "", ns)
                if "/api/errors" in url:
                    raise RuntimeError("arXiv returned an API error")
                source_id = re.sub(r"v\d+$", "", url.split("/abs/")[-1])
                yield Paper(
                    source="arXiv", source_id=source_id,
                    title=plain(item.findtext("a:title", "", ns)),
                    abstract=plain(item.findtext("a:summary", "", ns)),
                    authors=[plain(a.findtext("a:name", "", ns)) for a in item.findall("a:author", ns)],
                    published=source_date(item.findtext("a:published", "", ns)),
                    url=f"https://arxiv.org/abs/{quote(source_id, safe='/')}", kind="preprint",
                    # arxiv:doi identifies the JOURNAL version, not this preprint.
                    # Keep separate versions; deduplication uses the arXiv ID.
                )
            if (page + 1) * PAGE_SIZE >= total:
                break
            if not entries:
                raise RuntimeError("arXiv pagination returned an empty page before completion")
            self.sleep(3)
        else:
            raise RuntimeError("arXiv page limit reached; coverage is incomplete")


SOURCES = {"Crossref": "crossref", "Europe PMC": "europe_pmc", "arXiv": "arxiv"}
