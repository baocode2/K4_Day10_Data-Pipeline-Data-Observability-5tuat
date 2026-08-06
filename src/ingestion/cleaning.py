from __future__ import annotations

from datetime import UTC, datetime
from html import unescape
import json
from pathlib import Path
import re
from typing import Any, Iterable

import pandas as pd

from core.utils import ensure_parent, normalize_whitespace, write_json
from ingestion.crossref import PaperRecord


CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "authors_joined",
    "categories",
    "categories_joined",
    "primary_category",
    "published",
    "updated",
    "age_days",
    "summary_chars",
    "text_for_embedding",
    "abs_url",
    "pdf_url",
    "comment",
]
MIN_SUMMARY_CHARS = 100


def _clean_text(value: Any) -> str:
    """Return a compact string and tolerate imperfect raw snapshots."""
    if value is None or (not isinstance(value, (list, tuple, dict)) and pd.isna(value)):
        return ""
    return normalize_whitespace(str(value))


def _clean_markup_text(value: Any) -> str:
    """Remove Crossref XML/HTML tags and decode entities before normalization."""
    text = unescape(_clean_text(value))
    return normalize_whitespace(re.sub(r"<[^>]*>", " ", text))


def _clean_list(values: Iterable[Any] | Any) -> list[str]:
    """Normalize a list while preserving order and removing case-insensitive duplicates."""
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _parse_date(value: Any) -> pd.Timestamp | None:
    """Parse a source date as UTC; invalid or missing values are rejected."""
    cleaned = _clean_text(value)
    if not cleaned:
        return None
    parsed = pd.to_datetime(cleaned, errors="coerce", utc=True)
    if pd.isna(parsed):
        return None
    return parsed


def build_text_for_embedding(
    title: Any,
    summary: Any,
    authors_joined: Any = "",
    categories_joined: Any = "",
) -> str:
    """Build the exact retrieval text required by the clean-data contract."""
    del categories_joined  # Categories remain metadata, not embedding content.
    title_text = _clean_markup_text(title)
    authors_text = _clean_text(authors_joined)
    summary_text = _clean_markup_text(summary)
    return f"Title: {title_text} | Authors: {authors_text} | Summary: {summary_text}".rstrip()


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Normalize raw Crossref records into the stable dataframe used downstream.

    A valid row needs a stable ID, title, summary and parseable publication date.
    Duplicate IDs are matched case-insensitively and the first valid source row is
    kept. Cleaning statistics are attached to ``DataFrame.attrs`` so orchestration
    code can report raw-to-clean lineage without adding technical columns.
    """
    if run_date.tzinfo is None:
        run_timestamp = pd.Timestamp(run_date, tz=UTC)
    else:
        run_timestamp = pd.Timestamp(run_date).tz_convert(UTC)
    run_day = run_timestamp.normalize()

    rows: list[dict[str, Any]] = []
    rejected = {
        "missing_paper_id": 0,
        "missing_title": 0,
        "missing_summary": 0,
        "summary_too_short": 0,
        "invalid_published": 0,
    }

    for record in records:
        paper_id = _clean_text(record.paper_id)
        title = _clean_markup_text(record.title)
        summary = _clean_markup_text(record.summary)
        published_at = _parse_date(record.published)

        if not paper_id:
            rejected["missing_paper_id"] += 1
            continue
        if not title:
            rejected["missing_title"] += 1
            continue
        if not summary:
            rejected["missing_summary"] += 1
            continue
        if len(summary) < MIN_SUMMARY_CHARS:
            rejected["summary_too_short"] += 1
            continue
        if published_at is None:
            rejected["invalid_published"] += 1
            continue

        authors = _clean_list(record.authors)
        categories = _clean_list(record.categories)
        primary_category = _clean_text(record.primary_category)
        if primary_category and primary_category.casefold() not in {item.casefold() for item in categories}:
            categories.insert(0, primary_category)
        if not primary_category and categories:
            primary_category = categories[0]

        authors_joined = ", ".join(authors)
        categories_joined = ", ".join(categories)
        published = published_at.date().isoformat()
        updated_at = _parse_date(record.updated)
        updated = updated_at.date().isoformat() if updated_at is not None else published
        age_days = max(0, (run_day - published_at.normalize()).days)

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "authors_joined": authors_joined,
                "categories": categories,
                "categories_joined": categories_joined,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "age_days": age_days,
                "summary_chars": len(summary),
                "text_for_embedding": build_text_for_embedding(
                    title, summary, authors_joined, categories_joined
                ),
                "abs_url": _clean_text(record.abs_url),
                "pdf_url": _clean_text(record.pdf_url),
                "comment": _clean_text(record.comment),
            }
        )

    frame = pd.DataFrame(rows, columns=CLEAN_COLUMNS)
    before_deduplication = len(frame)
    if not frame.empty:
        frame["_paper_id_key"] = frame["paper_id"].str.casefold()
        frame = frame.drop_duplicates(subset="_paper_id_key", keep="first").drop(columns="_paper_id_key")
        frame = frame.sort_values(
            by=["published", "paper_id"], ascending=[False, True], kind="stable"
        ).reset_index(drop=True)

    frame.attrs["cleaning_report"] = {
        "run_date": run_timestamp.isoformat(),
        "input_records": len(records),
        "valid_before_deduplication": before_deduplication,
        "output_records": len(frame),
        "filtered_records": sum(rejected.values()),
        "duplicates_removed": before_deduplication - len(frame),
        "rejected": rejected,
        "rules": {
            "required_fields": ["paper_id", "title", "summary", "published"],
            "minimum_summary_chars": MIN_SUMMARY_CHARS,
            "duplicate_key": "paper_id (case-insensitive)",
        },
    }
    return frame


def save_dataframe_artifacts(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    """Persist a clean-schema dataframe as interoperable CSV and typed JSON."""
    missing = [column for column in CLEAN_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Cannot save dataframe artifacts; missing columns: {', '.join(missing)}")

    ordered = df.loc[:, CLEAN_COLUMNS].copy()
    csv_frame = ordered.copy()
    for column in ("authors", "categories"):
        csv_frame[column] = csv_frame[column].map(
            lambda value: json.dumps(value if isinstance(value, list) else [], ensure_ascii=False)
        )

    ensure_parent(Path(csv_path))
    csv_frame.to_csv(csv_path, index=False, encoding="utf-8")

    # DataFrame.to_json converts numpy/pandas scalar types into standard JSON
    # numbers while retaining authors/categories as arrays.
    json_records = json.loads(ordered.to_json(orient="records", force_ascii=False))
    write_json(Path(json_path), json_records)


def save_clean_dataframe(
    df: pd.DataFrame,
    csv_path: Path,
    json_path: Path,
    report_path: Path | None = None,
) -> None:
    """Persist clean CSV/JSON plus the raw-to-clean lineage report."""
    cleaning_report = df.attrs.get("cleaning_report")
    if not isinstance(cleaning_report, dict):
        raise ValueError(
            "Cannot save traceable clean artifacts; DataFrame.attrs['cleaning_report'] is missing."
        )
    save_dataframe_artifacts(df, csv_path, json_path)

    output_report_path = Path(report_path) if report_path else Path(json_path).with_name("cleaning_report.json")
    write_json(output_report_path, cleaning_report)
