from __future__ import annotations

from typing import Any

from core.utils import write_json


_METRIC_KEYS = (
    "retrieval_hit_rate",
    "mean_token_f1",
    "judge_accuracy",
    "mean_judge_score",
)


def _delta(value_a: Any, value_b: Any) -> float | None:
    try:
        return round(float(value_b) - float(value_a), 4)
    except (TypeError, ValueError):
        return None


def _failed_check_names(quality: dict[str, Any]) -> set[str]:
    return {
        str(check.get("name"))
        for check in quality.get("checks", []) or []
        if str(check.get("status", "")).lower() != "pass"
    }


def _corruption_to_signal(corruption_log: dict[str, Any], quality: dict[str, Any]) -> list[dict[str, Any]]:
    failed = _failed_check_names(quality)
    rows: list[dict[str, Any]] = []
    for event in corruption_log.get("events", []) or []:
        event_type = event.get("type", "unknown")
        record_ids = event.get("record_ids", []) or []
        related_checks: list[str] = []
        if event_type == "drop_latest_records":
            related_checks.extend(["row_count", "freshness_threshold", "age_days_valid"])
        elif event_type == "blank_summary":
            related_checks.extend(["summary_min_chars", "text_for_embedding_not_empty"])
        elif event_type == "inject_summary_noise":
            related_checks.append("summary_min_chars")
        elif event_type == "truncate_title":
            related_checks.append("title_not_null")
        elif event_type == "stale_published_date":
            related_checks.append("freshness_threshold")
        elif event_type == "duplicate_rows":
            related_checks.append("paper_id_unique")
        observed_fails = [name for name in related_checks if name in failed]
        rows.append(
            {
                "event_type": event_type,
                "affected_record_ids": record_ids,
                "expected_signal_checks": related_checks,
                "observed_failing_checks": observed_fails,
            }
        )
    return rows


def _metric_change_row(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
    repaired: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in _METRIC_KEYS:
        if key not in baseline and key not in corrupted and key not in repaired:
            continue
        rows.append(
            {
                "metric": key,
                "baseline": baseline.get(key),
                "corrupted": corrupted.get(key),
                "repaired": repaired.get(key),
                "delta_corrupt_minus_baseline": _delta(baseline.get(key), corrupted.get(key)),
                "delta_repair_minus_corrupt": _delta(corrupted.get(key), repaired.get(key)),
            }
        )
    return rows


def _unchanged_signals(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
    repaired: dict[str, Any],
) -> list[str]:
    unchanged: list[str] = []
    for key in _METRIC_KEYS:
        if key not in baseline:
            continue
        if corrupted.get(key) == baseline.get(key) and repaired.get(key) == baseline.get(key):
            unchanged.append(key)
    return unchanged


def build_signal_change(
    corruption_log: dict[str, Any],
    baseline_quality: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
) -> dict[str, Any]:
    """Aggregate corruption events with their observed quality/quality deltas.

    The intent is to make it easy to defend the conclusion that a specific
    defect actually moves the RAG agent. ``unchanged_signals`` lists metrics
    that did not shift, so the comparison report does not overreach.
    """
    return {
        "corruption_to_quality": _corruption_to_signal(corruption_log, corrupted_quality),
        "metric_change": _metric_change_row(baseline_metrics, corrupted_metrics, repaired_metrics),
        "unchanged_signals": _unchanged_signals(baseline_metrics, corrupted_metrics, repaired_metrics),
        "quality_summary": {
            "baseline_overall_pass": baseline_quality.get("overall_pass"),
            "corrupted_overall_pass": corrupted_quality.get("overall_pass"),
            "repaired_overall_pass": repaired_quality.get("overall_pass"),
        },
    }


def write_signal_change(
    output_path,
    corruption_log: dict[str, Any],
    baseline_quality: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
) -> dict[str, Any]:
    payload = build_signal_change(
        corruption_log=corruption_log,
        baseline_quality=baseline_quality,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_metrics,
        repaired_metrics=repaired_metrics,
    )
    write_json(output_path, payload)
    return payload
