from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from core.config import Settings
from core.utils import write_json


SUMMARY_MIN_CHARS = 50
MIN_ROWS = 8


def _check_row_count(df: pd.DataFrame) -> dict[str, Any]:
    observed = int(len(df))
    return {
        "name": "row_count",
        "status": "pass" if observed >= MIN_ROWS else "fail",
        "observed": observed,
        "expected": f">= {MIN_ROWS}",
        "message": f"dataset has {observed} rows",
    }


def _check_paper_id(df: pd.DataFrame) -> dict[str, Any]:
    null_count = int(df["paper_id"].isna().sum()) if "paper_id" in df.columns else int(len(df))
    duplicate_count = int(df["paper_id"].duplicated().sum()) if "paper_id" in df.columns else 0
    ok = null_count == 0 and duplicate_count == 0
    return {
        "name": "paper_id_unique",
        "status": "pass" if ok else "fail",
        "observed": {"null": null_count, "duplicate": duplicate_count},
        "expected": {"null": 0, "duplicate": 0},
        "message": f"paper_id nulls={null_count}, duplicates={duplicate_count}",
    }


def _check_title(df: pd.DataFrame) -> dict[str, Any]:
    if "title" not in df.columns:
        return {"name": "title_not_null", "status": "fail", "observed": None, "expected": "non-null", "message": "title column missing"}
    missing = int(df["title"].isna().sum() + (df["title"].astype(str).str.strip() == "").sum())
    return {
        "name": "title_not_null",
        "status": "pass" if missing == 0 else "fail",
        "observed": missing,
        "expected": 0,
        "message": f"rows with missing title = {missing}",
    }


def _check_summary(df: pd.DataFrame) -> dict[str, Any]:
    if "summary" not in df.columns:
        return {"name": "summary_min_chars", "status": "fail", "observed": None, "expected": f">= {SUMMARY_MIN_CHARS}", "message": "summary column missing"}
    lengths = df["summary"].fillna("").astype(str).str.len()
    below = int((lengths < SUMMARY_MIN_CHARS).sum())
    return {
        "name": "summary_min_chars",
        "status": "pass" if below == 0 else "fail",
        "observed": {"rows_below_threshold": below, "min_observed": int(lengths.min()) if len(lengths) else 0},
        "expected": {"rows_below_threshold": 0, "min_chars": SUMMARY_MIN_CHARS},
        "message": f"rows with summary < {SUMMARY_MIN_CHARS} chars = {below}",
    }


def _check_text_for_embedding(df: pd.DataFrame) -> dict[str, Any]:
    if "text_for_embedding" not in df.columns:
        return {"name": "text_for_embedding_not_empty", "status": "fail", "observed": None, "expected": "non-empty", "message": "text_for_embedding column missing"}
    empty = int(df["text_for_embedding"].fillna("").astype(str).str.strip().eq("").sum())
    return {
        "name": "text_for_embedding_not_empty",
        "status": "pass" if empty == 0 else "fail",
        "observed": empty,
        "expected": 0,
        "message": f"rows with empty text_for_embedding = {empty}",
    }


def _check_age_days(df: pd.DataFrame) -> dict[str, Any]:
    if "age_days" not in df.columns:
        return {"name": "age_days_valid", "status": "fail", "observed": None, "expected": "non-negative number", "message": "age_days column missing"}
    series = pd.to_numeric(df["age_days"], errors="coerce")
    invalid = int(series.isna().sum() + (series < 0).sum())
    return {
        "name": "age_days_valid",
        "status": "pass" if invalid == 0 else "fail",
        "observed": {"invalid_rows": invalid, "max_age_days": float(series.max()) if series.notna().any() else None},
        "expected": {"invalid_rows": 0, "min_age_days": 0},
        "message": f"rows with invalid age_days = {invalid}",
    }


def _check_freshness(df: pd.DataFrame, settings: Settings) -> dict[str, Any]:
    if "age_days" not in df.columns:
        return {"name": "freshness_threshold", "status": "fail", "observed": None, "expected": f"age_days <= {settings.freshness_threshold_days}", "message": "age_days column missing"}
    series = pd.to_numeric(df["age_days"], errors="coerce").fillna(0)
    stale = int((series > settings.freshness_threshold_days).sum())
    return {
        "name": "freshness_threshold",
        "status": "pass" if stale == 0 else "fail",
        "observed": {"stale_rows": stale, "threshold_days": settings.freshness_threshold_days},
        "expected": {"stale_rows": 0},
        "message": f"rows older than {settings.freshness_threshold_days} days = {stale}",
    }


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    checks = [
        _check_row_count(df),
        _check_paper_id(df),
        _check_title(df),
        _check_summary(df),
        _check_text_for_embedding(df),
        _check_age_days(df),
        _check_freshness(df, settings),
    ]
    payload = {
        "report_name": report_name,
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": int(len(df)),
        "checks": checks,
        "overall_pass": all(check["status"] == "pass" for check in checks),
    }
    output_path = settings.paths.quality_dir / f"{report_name}_quality.json"
    write_json(output_path, payload)
    return payload


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    if df.empty:
        payload = {
            "total_rows": 0,
            "latest_published": None,
            "oldest_published": None,
            "stale_rows": 0,
            "threshold_days": settings.freshness_threshold_days,
            "is_fresh": False,
            "generated_at": datetime.now(UTC).isoformat(),
        }
        write_json(report_path, payload)
        return payload

    published = pd.to_datetime(df["published"], errors="coerce", utc=True)
    age_days = pd.to_numeric(df["age_days"], errors="coerce")

    latest = published.max()
    oldest = published.min()
    stale_rows = int((age_days > settings.freshness_threshold_days).sum())

    payload = {
        "total_rows": int(len(df)),
        "latest_published": latest.isoformat() if pd.notna(latest) else None,
        "oldest_published": oldest.isoformat() if pd.notna(oldest) else None,
        "stale_rows": stale_rows,
        "threshold_days": settings.freshness_threshold_days,
        "is_fresh": stale_rows == 0,
        "generated_at": datetime.now(UTC).isoformat(),
    }
    write_json(report_path, payload)
    return payload
