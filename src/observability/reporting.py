from __future__ import annotations

from typing import Any

from core.utils import write_text


_METRIC_KEYS = (
    "samples",
    "retrieval_hit_rate",
    "mean_token_f1",
    "judge_accuracy",
    "mean_judge_score",
    "ragas",
)


def _fmt_float(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _fmt_status(status: Any) -> str:
    if isinstance(status, bool):
        return "PASS" if status else "FAIL"
    return "PASS" if str(status).lower() == "pass" else "FAIL"


def _quality_section(quality: dict[str, Any]) -> list[str]:
    lines: list[str] = ["## Data quality", ""]
    if not quality:
        lines.append("_No quality report provided._")
        return lines
    overall = _fmt_status(quality.get("overall_pass", False))
    lines.append(f"- Overall: **{overall}** (total_rows = {quality.get('total_rows', 'n/a')})")
    lines.append("")
    checks = quality.get("checks", []) or []
    if checks:
        lines.append("| Check | Status | Message |")
        lines.append("| --- | --- | --- |")
        for check in checks:
            lines.append(
                f"| {check.get('name', '?')} | {_fmt_status(check.get('status'))} | {check.get('message', '')} |"
            )
    lines.append("")
    return lines


def _freshness_section(freshness: dict[str, Any]) -> list[str]:
    lines: list[str] = ["## Freshness", ""]
    if not freshness:
        lines.append("_No freshness report provided._")
        return lines
    lines.append(f"- Total rows: {freshness.get('total_rows', 'n/a')}")
    lines.append(f"- Latest published: {freshness.get('latest_published', 'n/a')}")
    lines.append(f"- Oldest published: {freshness.get('oldest_published', 'n/a')}")
    lines.append(f"- Threshold days: {freshness.get('threshold_days', 'n/a')}")
    lines.append(f"- Stale rows: {freshness.get('stale_rows', 'n/a')}")
    lines.append(f"- Is fresh: **{_fmt_status(freshness.get('is_fresh', False))}**")
    lines.append("")
    return lines


def _metrics_table(metrics: dict[str, Any]) -> list[str]:
    lines: list[str] = ["## Evaluation metrics", ""]
    if not metrics:
        lines.append("_No metrics provided._")
        return lines
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    for key in _METRIC_KEYS:
        if key in metrics:
            value = metrics[key]
            if isinstance(value, dict):
                value_repr = ", ".join(f"{k}={v}" for k, v in value.items())
            else:
                value_repr = _fmt_float(value)
            lines.append(f"| {key} | {value_repr} |")
    lines.append("")
    return lines


def _source_section(source_summary: dict[str, Any]) -> list[str]:
    lines: list[str] = ["## Source", ""]
    if not source_summary:
        lines.append("_No source summary provided._")
        return lines
    for key, value in source_summary.items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    return lines


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    parts: list[str] = ["# Phase 1 - Baseline report", ""]
    parts.extend(_source_section(source_summary))
    parts.extend(_metrics_table(metrics))
    parts.extend(_quality_section(quality))
    parts.extend(_freshness_section(freshness))
    write_text(report_path, "\n".join(parts))


def _delta(value_a: Any, value_b: Any) -> str:
    try:
        return f"{float(value_b) - float(value_a):+.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _comparison_metrics_table(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
    repaired: dict[str, Any],
) -> list[str]:
    lines: list[str] = ["## Metrics comparison", ""]
    lines.append("| Metric | Baseline | Corrupted | Repaired | Δ (Corrupt-Base) | Δ (Repair-Corrupt) |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for key in _METRIC_KEYS:
        if key == "ragas":
            continue
        if key not in baseline and key not in corrupted and key not in repaired:
            continue
        b = _fmt_float(baseline.get(key))
        c = _fmt_float(corrupted.get(key))
        r = _fmt_float(repaired.get(key))
        lines.append(f"| {key} | {b} | {c} | {r} | {_delta(baseline.get(key), corrupted.get(key))} | {_delta(corrupted.get(key), repaired.get(key))} |")
    lines.append("")
    return lines


def _quality_comparison_table(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
    repaired: dict[str, Any],
) -> list[str]:
    lines: list[str] = ["## Quality comparison", ""]
    lines.append("| Stage | Overall | Total rows |")
    lines.append("| --- | --- | --- |")
    for stage, payload in (("baseline", baseline), ("corrupted", corrupted), ("repaired", repaired)):
        if not payload:
            lines.append(f"| {stage} | n/a | n/a |")
            continue
        lines.append(
            f"| {stage} | {_fmt_status(payload.get('overall_pass', False))} | {payload.get('total_rows', 'n/a')} |"
        )
    lines.append("")
    return lines


def _freshness_comparison_table(
    baseline: dict[str, Any],
    corrupted: dict[str, Any],
    repaired: dict[str, Any],
) -> list[str]:
    lines: list[str] = ["## Freshness comparison", ""]
    lines.append("| Stage | Is fresh | Stale rows | Latest published |")
    lines.append("| --- | --- | --- | --- |")
    for stage, payload in (("baseline", baseline), ("corrupted", corrupted), ("repaired", repaired)):
        if not payload:
            lines.append(f"| {stage} | n/a | n/a | n/a |")
            continue
        lines.append(
            f"| {stage} | {_fmt_status(payload.get('is_fresh', False))} | {payload.get('stale_rows', 'n/a')} | {payload.get('latest_published', 'n/a')} |"
        )
    lines.append("")
    return lines


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
) -> None:
    parts: list[str] = ["# Corruption - Repair comparison report", ""]
    parts.extend(
        _comparison_metrics_table(
            baseline_metrics,
            corrupted_metrics,
            repaired_metrics,
        )
    )
    parts.extend(
        _quality_comparison_table(
            baseline_quality or {},
            corrupted_quality,
            repaired_quality,
        )
    )
    parts.extend(
        _freshness_comparison_table(
            baseline_freshness or {},
            corrupted_freshness,
            repaired_freshness,
        )
    )
    write_text(report_path, "\n".join(parts))
