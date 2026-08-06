from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
import random
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, safe_slug, write_json

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
_RETRYABLE_STATUS_CODES = (429, 503)


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _date_parts_to_iso(date_field: dict | None) -> str:
    if not date_field:
        return ""
    parts_list = date_field.get("date-parts")
    if not parts_list or not parts_list[0]:
        return ""
    parts = parts_list[0]
    year = parts[0]
    month = parts[1] if len(parts) > 1 else 1
    day = parts[2] if len(parts) > 2 else 1
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return f"{year:04d}-01-01"


def _extract_published(item: dict) -> str:
    for key in ("published", "published-print", "published-online", "issued", "created"):
        iso = _date_parts_to_iso(item.get(key))
        if iso:
            return iso
    return ""


def _extract_updated(item: dict, published: str) -> str:
    iso = _date_parts_to_iso(item.get("indexed")) or _date_parts_to_iso(item.get("deposited"))
    return iso or published


def _build_authors(author_list: list[dict]) -> list[str]:
    authors = []
    for author in author_list:
        given = (author.get("given") or "").strip()
        family = (author.get("family") or "").strip()
        name = f"{given} {family}".strip()
        if not name:
            name = (author.get("name") or "").strip()
        if name:
            authors.append(name)
    return authors


def _find_pdf_link(links: list[dict]) -> str:
    for link in links:
        if link.get("content-type") == "application/pdf":
            return link.get("URL", "")
    return ""


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord."""
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        doi = item.get("DOI")
        titles = item.get("title") or []
        abstract_raw = item.get("abstract")
        if not doi or not titles or not abstract_raw:
            continue  # thieu field bat buoc -> loai

        title = normalize_whitespace(titles[0])
        summary = normalize_whitespace(re.sub(r"<[^>]+>", "", abstract_raw))
        if not title or not summary:
            continue

        categories = item.get("subject", [])
        published = _extract_published(item)
        updated = _extract_updated(item, published)

        records.append(
            PaperRecord(
                paper_id=safe_slug(doi),
                title=title,
                summary=summary,
                authors=_build_authors(item.get("author", [])),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=updated,
                abs_url=item.get("URL", ""),
                pdf_url=_find_pdf_link(item.get("link", [])),
                comment=(item.get("container-title") or [""])[0],
            )
        )

    return records


def _get_with_retry(url: str, params: dict, max_retries: int = 5, base_delay: float = 1.0) -> dict:
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = requests.get(
                url,
                params=params,
                headers={"User-Agent": "day10-pipeline (mailto:student@example.com)"},
                timeout=30,
            )
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(base_delay * (2**attempt) + random.uniform(0, 0.5))
            continue

        if response.status_code == 200:
            return response.json()

        if response.status_code in _RETRYABLE_STATUS_CODES:
            retry_after = response.headers.get("Retry-After")
            delay = float(retry_after) if retry_after else base_delay * (2**attempt)
            time.sleep(delay + random.uniform(0, 0.5))
            continue

        response.raise_for_status()

    raise RuntimeError(f"Crossref API failed after {max_retries} retries") from last_error


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi Crossref API, luu raw response, parse thanh records."""
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
    }

    payload = _get_with_retry(CROSSREF_WORKS_URL, params)
    write_json(settings.paths.raw_api_response, payload)

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh PaperRecord."""
    raw = read_json(path)
    return [PaperRecord(**item) for item in raw]