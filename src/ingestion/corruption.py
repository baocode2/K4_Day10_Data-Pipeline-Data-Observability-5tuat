from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from core.utils import write_json
from ingestion.cleaning import build_text_for_embedding


NOISE_SUFFIX = " [CORRUPTED_NOISE] zxqv 000 !!! unrelated-token-stream"


def _sample_indices(df: pd.DataFrame, count: int, offset: int = 0) -> list[int]:
    """Choose deterministic rows and wrap for tiny datasets."""
    if df.empty or count <= 0:
        return []
    ordered = list(df.index)
    return [ordered[(offset + position) % len(ordered)] for position in range(min(count, len(ordered)))]


def _scenario_size(row_count: int) -> int:
    if row_count <= 0:
        return 0
    return max(1, min(3, row_count // 8 or 1))


def _rebuild_derived_columns(df: pd.DataFrame) -> None:
    df["summary_chars"] = df["summary"].fillna("").astype(str).str.len()
    df["text_for_embedding"] = df.apply(
        lambda row: build_text_for_embedding(
            row.get("title", ""),
            row.get("summary", ""),
            row.get("authors_joined", ""),
            row.get("categories_joined", ""),
        ),
        axis=1,
    )


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: Path) -> pd.DataFrame:
    """Create deterministic, auditable data defects without mutating baseline data.

    The function deliberately introduces completeness, validity, freshness and
    uniqueness failures. Every affected ID and parameter is written to the log,
    allowing quality changes to be connected back to a specific corruption.
    """
    required = {
        "paper_id",
        "title",
        "summary",
        "published",
        "age_days",
        "authors_joined",
        "categories_joined",
        "text_for_embedding",
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Cannot corrupt dataframe; missing clean columns: {', '.join(missing)}")
    if df.empty:
        raise ValueError("Cannot corrupt an empty clean dataframe.")

    corrupted = df.copy(deep=True).reset_index(drop=True)
    before_count = len(corrupted)
    scenario_count = _scenario_size(before_count)
    events: list[dict[str, Any]] = []

    published = pd.to_datetime(corrupted["published"], errors="coerce", utc=True)
    # Keep at least one row so the remaining defect types are observable even in
    # a very small validation sample.
    drop_count = min(scenario_count, max(0, before_count - 1))
    latest_indices = published.sort_values(ascending=False, na_position="last").index[:drop_count].tolist()
    dropped_ids = corrupted.loc[latest_indices, "paper_id"].astype(str).tolist()
    corrupted = corrupted.drop(index=latest_indices).reset_index(drop=True)
    events.append(
        {
            "type": "drop_latest_records",
            "record_ids": dropped_ids,
            "parameters": {"count": len(dropped_ids)},
            "before_count": before_count,
            "after_count": len(corrupted),
        }
    )

    # Keep scenario selection stable and mostly disjoint on normal lab-sized data.
    blank_indices = _sample_indices(corrupted, scenario_count, 0)
    noise_indices = _sample_indices(corrupted, scenario_count, scenario_count)
    title_indices = _sample_indices(corrupted, scenario_count, scenario_count * 2)
    stale_indices = _sample_indices(corrupted, scenario_count, scenario_count * 3)

    blank_ids = corrupted.loc[blank_indices, "paper_id"].astype(str).tolist()
    corrupted.loc[blank_indices, "summary"] = ""
    events.append(
        {
            "type": "blank_summary",
            "record_ids": blank_ids,
            "parameters": {"replacement": ""},
            "before_count": len(corrupted),
            "after_count": len(corrupted),
        }
    )

    noise_ids = corrupted.loc[noise_indices, "paper_id"].astype(str).tolist()
    corrupted.loc[noise_indices, "summary"] = (
        corrupted.loc[noise_indices, "summary"].fillna("").astype(str) + NOISE_SUFFIX
    )
    events.append(
        {
            "type": "inject_summary_noise",
            "record_ids": noise_ids,
            "parameters": {"suffix": NOISE_SUFFIX},
            "before_count": len(corrupted),
            "after_count": len(corrupted),
        }
    )

    title_ids = corrupted.loc[title_indices, "paper_id"].astype(str).tolist()
    corrupted.loc[title_indices, "title"] = corrupted.loc[title_indices, "title"].map(
        lambda value: str(value)[:12].rstrip()
    )
    events.append(
        {
            "type": "truncate_title",
            "record_ids": title_ids,
            "parameters": {"max_chars": 12},
            "before_count": len(corrupted),
            "after_count": len(corrupted),
        }
    )

    stale_ids = corrupted.loc[stale_indices, "paper_id"].astype(str).tolist()
    stale_dates = pd.to_datetime(corrupted.loc[stale_indices, "published"], errors="coerce")
    original_ages = pd.to_numeric(corrupted.loc[stale_indices, "age_days"], errors="coerce").fillna(0)
    shifted_dates = stale_dates.map(
        lambda value: value - pd.DateOffset(years=10) if not pd.isna(value) else pd.Timestamp("2000-01-01")
    )
    corrupted.loc[stale_indices, "published"] = stale_dates.map(
        lambda value: (value - pd.DateOffset(years=10)).date().isoformat() if not pd.isna(value) else "2000-01-01"
    )
    extra_age = pd.Series(
        [(old - new).days if not pd.isna(old) else 99999 for old, new in zip(stale_dates, shifted_dates)],
        index=stale_dates.index,
    )
    corrupted.loc[stale_indices, "age_days"] = (original_ages + extra_age).astype(int)
    events.append(
        {
            "type": "stale_published_date",
            "record_ids": stale_ids,
            "parameters": {"years_subtracted": 10},
            "before_count": len(corrupted),
            "after_count": len(corrupted),
        }
    )

    duplicate_indices = _sample_indices(corrupted, scenario_count, scenario_count * 4)
    duplicate_ids = corrupted.loc[duplicate_indices, "paper_id"].astype(str).tolist()
    count_before_duplicates = len(corrupted)
    corrupted = pd.concat([corrupted, corrupted.loc[duplicate_indices].copy()], ignore_index=True)
    events.append(
        {
            "type": "duplicate_rows",
            "record_ids": duplicate_ids,
            "parameters": {"copies_added": len(duplicate_indices)},
            "before_count": count_before_duplicates,
            "after_count": len(corrupted),
        }
    )

    _rebuild_derived_columns(corrupted)
    corrupted = corrupted.reset_index(drop=True)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "input_rows": before_count,
        "output_rows": len(corrupted),
        "events": events,
        "summary": {event["type"]: len(event["record_ids"]) for event in events},
    }
    write_json(Path(output_log_path), payload)
    return corrupted
