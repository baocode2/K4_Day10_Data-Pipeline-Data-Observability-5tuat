from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import load_settings
from core.utils import now_utc, read_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import CLEAN_COLUMNS, build_clean_dataframe, save_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _load_clean_dataframe(json_path: Path) -> pd.DataFrame:
    records = read_json(json_path)
    return pd.DataFrame(records, columns=CLEAN_COLUMNS)


def _dedupe_for_index(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicate paper_id rows before embedding.

    The `duplicate_rows` corruption scenario intentionally inserts duplicate
    paper_id rows so `run_data_quality_checks` can catch them. The RAG index
    contract (`validate_index_dataframe`) rejects duplicate paper_id outright,
    so we index a deduped view while the corrupted CSV/JSON and quality
    checks still see every duplicate row.
    """
    keys = df["paper_id"].astype(str).str.casefold()
    return df.loc[~keys.duplicated(keep="first")].reset_index(drop=True)


def main() -> None:
    settings = load_settings()

    if not settings.paths.clean_json.exists() or not settings.paths.baseline_metrics.exists():
        raise RuntimeError(
            "Baseline artifacts not found. Run `python script/run_phase1.py` before the corruption flow."
        )

    print("1/11 Loading baseline clean dataset and metrics...")
    baseline_df = _load_clean_dataframe(settings.paths.clean_json)
    baseline_metrics = read_json(settings.paths.baseline_metrics)
    print(f"    baseline: {len(baseline_df)} clean records")

    print("2/11 Corrupting baseline dataset...")
    corrupted_df = corrupt_clean_dataframe(baseline_df, settings.paths.corruption_log)
    corrupted_df.attrs["cleaning_report"] = read_json(settings.paths.corruption_log)
    save_clean_dataframe(
        corrupted_df,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
        report_path=settings.paths.clean_json.parent / "corrupted_cleaning_report.json",
    )
    print(f"    {len(baseline_df)} -> {len(corrupted_df)} rows, log: {settings.paths.corruption_log}")

    print("3/11 Building corrupted embedding index...")
    corrupted_index = LocalEmbeddingIndex.build(
        _dedupe_for_index(corrupted_df), settings, embeddings_output_path=settings.paths.corrupted_embeddings_json
    )
    print(f"    collection={corrupted_index.collection_name} documents={len(corrupted_index.documents)}")

    print("4/11 Evaluating corrupted dataset...")
    corrupted_bundle = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )
    print(
        f"    retrieval_hit_rate={corrupted_bundle.summary['retrieval_hit_rate']:.4f} "
        f"mean_token_f1={corrupted_bundle.summary['mean_token_f1']:.4f}"
    )

    print("5/11 Running data quality checks on corrupted dataset...")
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, report_name="corrupted")
    print(f"    overall_pass={corrupted_quality['overall_pass']}")

    print("6/11 Building freshness report for corrupted dataset...")
    corrupted_freshness = build_freshness_report(
        corrupted_df, settings, settings.paths.quality_dir / "corrupted_freshness_report.json"
    )
    print(f"    is_fresh={corrupted_freshness['is_fresh']} stale_rows={corrupted_freshness['stale_rows']}")

    print("7/11 Repairing dataset from raw source...")
    raw_records = load_raw_records(settings.paths.raw_records_json)
    repaired_df = build_clean_dataframe(raw_records, run_date=now_utc())
    save_clean_dataframe(
        repaired_df,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
        report_path=settings.paths.clean_json.parent / "repaired_cleaning_report.json",
    )
    print(f"    repaired from {len(raw_records)} raw records -> {len(repaired_df)} clean records")

    print("8/11 Building repaired embedding index...")
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df, settings, embeddings_output_path=settings.paths.repaired_embeddings_json
    )
    print(f"    collection={repaired_index.collection_name} documents={len(repaired_index.documents)}")

    print("9/11 Evaluating repaired dataset...")
    repaired_bundle = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )
    print(
        f"    retrieval_hit_rate={repaired_bundle.summary['retrieval_hit_rate']:.4f} "
        f"mean_token_f1={repaired_bundle.summary['mean_token_f1']:.4f}"
    )

    print("10/11 Running data quality and freshness checks on repaired dataset...")
    repaired_quality = run_data_quality_checks(repaired_df, settings, report_name="repaired")
    repaired_freshness = build_freshness_report(
        repaired_df, settings, settings.paths.quality_dir / "repaired_freshness_report.json"
    )
    print(
        f"    overall_pass={repaired_quality['overall_pass']} "
        f"is_fresh={repaired_freshness['is_fresh']} stale_rows={repaired_freshness['stale_rows']}"
    )

    print("11/11 Writing comparison report...")
    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_bundle.summary,
        repaired_metrics=repaired_bundle.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )
    print(f"    report: {settings.paths.comparison_report}")

    print("\nCorruption/repair flow complete.")
