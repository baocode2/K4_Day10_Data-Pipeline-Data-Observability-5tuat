from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from ingestion.cleaning import MIN_SUMMARY_CHARS, build_text_for_embedding


def _checks_by_name(quality: dict[str, Any]) -> dict[str, dict[str, Any]]:
    checks = quality.get("checks", [])
    if not isinstance(checks, list):
        raise ValueError("CP3 validation failed: quality checks must be a list.")
    result = {str(check.get("name")): check for check in checks}
    if len(result) != len(checks):
        raise ValueError("CP3 validation failed: quality check names are duplicated.")
    return result


def validate_cp3_clean_quality(
    clean_df: pd.DataFrame,
    cleaning_report: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    """Recompute Role 3 signals and prove CP3 reports match clean data."""
    row_count = len(clean_df)
    input_count = int(cleaning_report.get("input_records", -1))
    accounted = (
        int(cleaning_report.get("output_records", -1))
        + int(cleaning_report.get("filtered_records", -1))
        + int(cleaning_report.get("duplicates_removed", -1))
    )
    if input_count != accounted or int(cleaning_report.get("output_records", -1)) != row_count:
        raise ValueError("CP3 validation failed: raw-to-clean lineage counts do not balance.")

    paper_ids = clean_df["paper_id"].astype(str).str.strip()
    if paper_ids.eq("").any() or paper_ids.str.casefold().duplicated().any():
        raise ValueError("CP3 validation failed: paper_id is blank or duplicated.")
    if clean_df["summary"].astype(str).str.len().lt(MIN_SUMMARY_CHARS).any():
        raise ValueError("CP3 validation failed: a summary violates the clean minimum length.")

    expected_text = clean_df.apply(
        lambda row: build_text_for_embedding(
            row["title"], row["summary"], row["authors_joined"], row["categories_joined"]
        ),
        axis=1,
    )
    if not expected_text.equals(clean_df["text_for_embedding"].astype(str)):
        raise ValueError("CP3 validation failed: text_for_embedding does not match clean fields.")
    expected_summary_chars = clean_df["summary"].astype(str).str.len()
    if not expected_summary_chars.equals(pd.to_numeric(clean_df["summary_chars"]).astype(int)):
        raise ValueError("CP3 validation failed: summary_chars is incorrect.")

    run_day = pd.Timestamp(cleaning_report["run_date"]).tz_convert("UTC").normalize()
    published = pd.to_datetime(clean_df["published"], errors="coerce", utc=True)
    if published.isna().any():
        raise ValueError("CP3 validation failed: published contains invalid dates.")
    expected_age = published.map(lambda value: max(0, (run_day - value.normalize()).days))
    observed_age = pd.to_numeric(clean_df["age_days"], errors="coerce")
    if observed_age.isna().any() or not expected_age.equals(observed_age.astype(int)):
        raise ValueError("CP3 validation failed: age_days does not match published/run_date.")

    checks = _checks_by_name(quality)
    required_checks = {
        "row_count",
        "paper_id_unique",
        "title_not_null",
        "summary_min_chars",
        "text_for_embedding_not_empty",
        "age_days_valid",
        "freshness_threshold",
    }
    if required_checks.difference(checks):
        raise ValueError("CP3 validation failed: baseline quality checks are incomplete.")
    if int(quality.get("total_rows", -1)) != row_count:
        raise ValueError("CP3 validation failed: quality row count differs from clean data.")
    if checks["summary_min_chars"].get("expected", {}).get("min_chars") != MIN_SUMMARY_CHARS:
        raise ValueError("CP3 validation failed: quality summary threshold differs from cleaning.")

    stale_rows = int((observed_age > settings.freshness_threshold_days).sum())
    expected_quality_values = {
        "row_count": row_count,
        "text_for_embedding_not_empty": int(clean_df["text_for_embedding"].astype(str).str.strip().eq("").sum()),
    }
    for name, observed in expected_quality_values.items():
        if checks[name].get("observed") != observed:
            raise ValueError(f"CP3 validation failed: quality signal {name} is incorrect.")
    if checks["freshness_threshold"].get("observed", {}).get("stale_rows") != stale_rows:
        raise ValueError("CP3 validation failed: quality stale-row count is incorrect.")
    if not quality.get("overall_pass") or any(check.get("status") != "pass" for check in checks.values()):
        raise ValueError("CP3 validation failed: baseline quality does not pass.")

    latest = published.max().isoformat()
    oldest = published.min().isoformat()
    expected_freshness = {
        "total_rows": row_count,
        "latest_published": latest,
        "oldest_published": oldest,
        "stale_rows": stale_rows,
        "threshold_days": settings.freshness_threshold_days,
        "is_fresh": stale_rows == 0,
    }
    for key, expected in expected_freshness.items():
        if freshness.get(key) != expected:
            raise ValueError(f"CP3 validation failed: freshness field {key} is incorrect.")

    return {
        "status": "pass",
        "clean_rows": row_count,
        "lineage_input_rows": input_count,
        "summary_min_chars": MIN_SUMMARY_CHARS,
        "max_age_days": int(observed_age.max()),
        "stale_rows": stale_rows,
        "quality_checks": len(checks),
    }
