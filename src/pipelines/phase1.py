from __future__ import annotations

from core.config import load_settings
from core.utils import now_utc, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe, save_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.agent import build_agent, run_agent_question
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()

    print("1/9 Loading raw records...")
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        records = fetch_source_records(settings)
    else:
        records = load_raw_records(settings.paths.raw_records_json)
    print(f"    {len(records)} raw records")

    print("2/9 Cleaning data...")
    clean_df = build_clean_dataframe(records, run_date=now_utc())
    save_clean_dataframe(clean_df, settings.paths.clean_csv, settings.paths.clean_json)
    print(f"    {len(clean_df)} clean records")

    print("3/9 Building baseline embedding index...")
    index = LocalEmbeddingIndex.build(clean_df, settings)
    print(f"    collection={index.collection_name} documents={len(index.documents)}")

    print("4/9 Preparing evaluation test set...")
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        build_test_set(clean_df, settings.paths.eval_testset)
    print(f"    test set: {settings.paths.eval_testset}")

    print("5/9 Evaluating baseline...")
    bundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )
    print(
        f"    retrieval_hit_rate={bundle.summary['retrieval_hit_rate']:.4f} "
        f"mean_token_f1={bundle.summary['mean_token_f1']:.4f}"
    )

    print("6/9 Running data quality checks...")
    quality = run_data_quality_checks(clean_df, settings, report_name="baseline")
    print(f"    overall_pass={quality['overall_pass']}")

    print("7/9 Building freshness report...")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)
    print(f"    is_fresh={freshness['is_fresh']} stale_rows={freshness['stale_rows']}")

    print("8/9 Writing phase1 report...")
    source_summary = {
        "source_api": settings.source_api,
        "query": settings.source_query,
        "filter": settings.source_filter,
        "raw_records": len(records),
        "clean_records": len(clean_df),
        "collection_name": index.collection_name,
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=bundle.summary,
        quality=quality,
        freshness=freshness,
    )
    print(f"    report: {settings.paths.baseline_report}")

    print("9/9 Demoing agent on sample questions...")
    demo_answers: list[dict[str, str]] = []
    try:
        agent = build_agent(settings, index)
        for item in bundle.answers[:2]:
            demo_answers.append(
                {
                    "question": item["question"],
                    "agent_answer": run_agent_question(agent, item["question"]),
                }
            )
    except Exception as exc:  # demo is illustrative only; never fail the baseline run on it
        demo_answers = [{"error": str(exc)}]
    write_json(settings.paths.demo_answers, demo_answers)
    print(f"    demo answers: {settings.paths.demo_answers}")

    print("\nBaseline pipeline complete.")
