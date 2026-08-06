from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
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


def _clean_text(value: Any) -> str:
    """Return a compact string and tolerate imperfect raw snapshots."""
    if value is None or (not isinstance(value, (list, tuple, dict)) and pd.isna(value)):
        return ""
    return normalize_whitespace(str(value))


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
    """Build the single, labelled document consumed by MiniLM/Chroma."""
    def labelled(label: str, value: Any) -> str:
        cleaned = _clean_text(value)
        return f"{label}: {cleaned}" if cleaned else f"{label}:"

    parts = [
        labelled("Title", title),
        labelled("Authors", authors_joined),
        labelled("Categories", categories_joined),
        labelled("Summary", summary),
    ]
    return "\n".join(parts)


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
        "invalid_published": 0,
    }

    for record in records:
        paper_id = _clean_text(record.paper_id)
        title = _clean_text(record.title)
        summary = _clean_text(record.summary)
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
        "input_records": len(records),
        "valid_before_deduplication": before_deduplication,
        "output_records": len(frame),
        "duplicates_removed": before_deduplication - len(frame),
        "rejected": rejected,
    }
    return frame


def save_clean_dataframe(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    """Persist the clean contract as interoperable CSV and typed JSON artifacts."""
    missing = [column for column in CLEAN_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Cannot save clean dataframe; missing columns: {', '.join(missing)}")

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
