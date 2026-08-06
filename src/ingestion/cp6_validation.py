from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import NOISE_SUFFIX
from ingestion.crossref import PaperRecord


METRIC_KEYS = (
    "retrieval_hit_rate",
    "mean_token_f1",
    "judge_accuracy",
    "mean_judge_score",
)


def _assert_frames_equal(left: pd.DataFrame, right: pd.DataFrame, message: str) -> None:
    try:
        pd.testing.assert_frame_equal(
            left.reset_index(drop=True),
            right.reset_index(drop=True),
            check_dtype=False,
        )
    except AssertionError as exc:
        raise ValueError(message) from exc


def _manifest_ids(manifest: dict[str, Any]) -> list[str]:
    documents = manifest.get("documents", [])
    if not isinstance(documents, list):
        raise ValueError("CP6 validation failed: embedding manifest documents are invalid.")
    return [str(document.get("paper_id", "")) for document in documents]


def validate_cp6_repair(
    raw_records: list[PaperRecord],
    baseline: pd.DataFrame,
    corrupted: pd.DataFrame,
    repaired: pd.DataFrame,
    repaired_cleaning_report: dict[str, Any],
    corruption_log: dict[str, Any],
    baseline_quality: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    baseline_freshness: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    baseline_manifest: dict[str, Any],
    repaired_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Prove repair was rebuilt from raw and recovered baseline data/signals."""
    run_date = datetime.fromisoformat(str(repaired_cleaning_report["run_date"]))
    rebuilt_from_raw = build_clean_dataframe(raw_records, run_date)
    _assert_frames_equal(
        rebuilt_from_raw,
        repaired,
        "CP6 validation failed: repaired artifact was not reproduced from raw records.",
    )
    _assert_frames_equal(
        baseline,
        repaired,
        "CP6 validation failed: repaired data does not match baseline.",
    )
    if baseline.equals(corrupted):
        raise ValueError("CP6 validation failed: corrupted data unexpectedly matches baseline.")

    if int(repaired_cleaning_report.get("input_records", -1)) != len(raw_records):
        raise ValueError("CP6 validation failed: repaired lineage input count is incorrect.")
    if int(repaired_cleaning_report.get("output_records", -1)) != len(repaired):
        raise ValueError("CP6 validation failed: repaired lineage output count is incorrect.")
    if repaired["paper_id"].astype(str).str.casefold().duplicated().any():
        raise ValueError("CP6 validation failed: repaired paper IDs are duplicated.")
    if repaired["summary"].astype(str).str.contains(NOISE_SUFFIX, regex=False).any():
        raise ValueError("CP6 validation failed: repaired summaries still contain corruption noise.")

    repaired_by_id = {str(row["paper_id"]): row for _, row in repaired.iterrows()}
    for event in corruption_log.get("events", []):
        for paper_id in event.get("record_ids", []):
            if str(paper_id) not in repaired_by_id:
                raise ValueError(f"CP6 validation failed: affected ID {paper_id} was not restored.")

    if baseline_quality.get("overall_pass") is not True:
        raise ValueError("CP6 validation failed: baseline quality does not pass.")
    if corrupted_quality.get("overall_pass") is not False:
        raise ValueError("CP6 validation failed: corrupted quality did not fail.")
    if repaired_quality.get("overall_pass") is not True:
        raise ValueError("CP6 validation failed: repaired quality does not pass.")
    freshness_states = (
        baseline_freshness.get("is_fresh"),
        corrupted_freshness.get("is_fresh"),
        repaired_freshness.get("is_fresh"),
    )
    if freshness_states != (True, False, True):
        raise ValueError("CP6 validation failed: freshness did not follow pass/fail/pass.")

    metric_deltas: dict[str, dict[str, float]] = {}
    for key in METRIC_KEYS:
        baseline_value = float(baseline_metrics[key])
        corrupted_value = float(corrupted_metrics[key])
        repaired_value = float(repaired_metrics[key])
        if abs(repaired_value - baseline_value) > 1e-12:
            raise ValueError(f"CP6 validation failed: repaired metric {key} did not recover baseline.")
        metric_deltas[key] = {
            "corruption_delta": corrupted_value - baseline_value,
            "repair_delta": repaired_value - corrupted_value,
        }
    if not any(delta["corruption_delta"] < 0 for delta in metric_deltas.values()):
        raise ValueError("CP6 validation failed: no evaluated metric degraded after corruption.")

    baseline_ids = _manifest_ids(baseline_manifest)
    repaired_ids = _manifest_ids(repaired_manifest)
    if len(baseline_ids) != len(baseline) or len(repaired_ids) != len(repaired):
        raise ValueError("CP6 validation failed: embedding manifest counts are incorrect.")
    if set(baseline_ids) != set(repaired_ids) or set(repaired_ids) != set(repaired["paper_id"].astype(str)):
        raise ValueError("CP6 validation failed: repaired manifest IDs differ from repaired data.")
    if repaired_manifest.get("collection_name") != "papers-repaired":
        raise ValueError("CP6 validation failed: repaired collection name is incorrect.")

    return {
        "status": "pass",
        "raw_records": len(raw_records),
        "baseline_rows": len(baseline),
        "corrupted_rows": len(corrupted),
        "repaired_rows": len(repaired),
        "repaired_equals_baseline": True,
        "quality_states": ["pass", "fail", "pass"],
        "freshness_states": ["fresh", "stale", "fresh"],
        "metric_deltas": metric_deltas,
        "repaired_collection": repaired_manifest["collection_name"],
    }
