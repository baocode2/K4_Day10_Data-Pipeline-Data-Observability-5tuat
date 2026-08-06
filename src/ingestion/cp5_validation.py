from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings
from ingestion.cleaning import build_text_for_embedding
from ingestion.corruption import NOISE_SUFFIX


EXPECTED_EVENT_TYPES = (
    "drop_latest_records",
    "blank_summary",
    "inject_summary_noise",
    "truncate_title",
    "stale_published_date",
    "duplicate_rows",
)


def validate_cp5_corruption(
    baseline: pd.DataFrame,
    corrupted: pd.DataFrame,
    corruption_log: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
    settings: Settings,
) -> dict[str, Any]:
    """Prove every logged CP5 corruption exists and baseline stayed clean."""
    events = corruption_log.get("events", [])
    event_map = {event.get("type"): event for event in events}
    if tuple(event_map) != EXPECTED_EVENT_TYPES or len(events) != len(EXPECTED_EVENT_TYPES):
        raise ValueError("CP5 validation failed: corruption event set/order is invalid.")
    if int(corruption_log.get("input_rows", -1)) != len(baseline):
        raise ValueError("CP5 validation failed: log input count differs from baseline.")
    if int(corruption_log.get("output_rows", -1)) != len(corrupted):
        raise ValueError("CP5 validation failed: log output count differs from corrupted data.")

    baseline_ids = baseline["paper_id"].astype(str)
    if baseline_ids.str.casefold().duplicated().any() or baseline["summary"].eq("").any():
        raise ValueError("CP5 validation failed: baseline was modified or is not clean.")

    by_id = {paper_id: group for paper_id, group in corrupted.groupby("paper_id", sort=False)}
    dropped = event_map["drop_latest_records"]["record_ids"]
    if any(paper_id in by_id for paper_id in dropped):
        raise ValueError("CP5 validation failed: a logged dropped ID still exists.")

    blanked = event_map["blank_summary"]["record_ids"]
    if any(paper_id not in by_id or not by_id[paper_id]["summary"].eq("").all() for paper_id in blanked):
        raise ValueError("CP5 validation failed: blank-summary corruption does not match log.")

    noised = event_map["inject_summary_noise"]["record_ids"]
    if any(
        paper_id not in by_id
        or not by_id[paper_id]["summary"].astype(str).str.contains(NOISE_SUFFIX, regex=False).all()
        for paper_id in noised
    ):
        raise ValueError("CP5 validation failed: noise corruption does not match log.")

    truncated = event_map["truncate_title"]["record_ids"]
    max_chars = int(event_map["truncate_title"]["parameters"]["max_chars"])
    if any(paper_id not in by_id or by_id[paper_id]["title"].astype(str).str.len().gt(max_chars).any() for paper_id in truncated):
        raise ValueError("CP5 validation failed: title truncation does not match log.")

    stale = event_map["stale_published_date"]["record_ids"]
    if any(
        paper_id not in by_id
        or pd.to_numeric(by_id[paper_id]["age_days"], errors="coerce").le(settings.freshness_threshold_days).any()
        for paper_id in stale
    ):
        raise ValueError("CP5 validation failed: stale-date corruption does not match log.")

    duplicated = event_map["duplicate_rows"]["record_ids"]
    if any(paper_id not in by_id or len(by_id[paper_id]) < 2 for paper_id in duplicated):
        raise ValueError("CP5 validation failed: duplicate corruption does not match log.")

    expected_text = corrupted.apply(
        lambda row: build_text_for_embedding(
            row["title"], row["summary"], row["authors_joined"], row["categories_joined"]
        ),
        axis=1,
    )
    if not expected_text.equals(corrupted["text_for_embedding"].astype(str)):
        raise ValueError("CP5 validation failed: corrupted embedding text was not rebuilt.")

    checks = {check["name"]: check for check in quality.get("checks", [])}
    expected_failures = {"paper_id_unique", "summary_min_chars", "freshness_threshold"}
    actual_failures = {name for name, check in checks.items() if check.get("status") == "fail"}
    if not expected_failures.issubset(actual_failures) or quality.get("overall_pass") is not False:
        raise ValueError("CP5 validation failed: quality gates did not detect corruption.")
    stale_rows = int((pd.to_numeric(corrupted["age_days"], errors="coerce") > settings.freshness_threshold_days).sum())
    if freshness.get("stale_rows") != stale_rows or freshness.get("is_fresh") is not False:
        raise ValueError("CP5 validation failed: freshness report does not match corrupted data.")

    return {
        "status": "pass",
        "baseline_rows": len(baseline),
        "corrupted_rows": len(corrupted),
        "event_counts": {name: len(event_map[name]["record_ids"]) for name in EXPECTED_EVENT_TYPES},
        "quality_failures": sorted(actual_failures),
        "stale_rows": stale_rows,
    }
