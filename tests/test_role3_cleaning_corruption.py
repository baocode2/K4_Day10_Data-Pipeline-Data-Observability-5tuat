from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

import pandas as pd
import pytest

from core.config import load_settings
from core.utils import read_json
from ingestion.cleaning import (
    CLEAN_COLUMNS,
    build_clean_dataframe,
    save_clean_dataframe,
    save_dataframe_artifacts,
)
from ingestion.corruption import NOISE_SUFFIX, corrupt_clean_dataframe
from ingestion.cp2_validation import validate_cp2_handoff
from ingestion.cp5_validation import validate_cp5_corruption
from ingestion.cp6_validation import validate_cp6_repair
from evaluation.testset import build_test_set
from ingestion.crossref import PaperRecord, load_raw_records, parse_crossref_payload


def paper(number: int, **overrides) -> PaperRecord:
    values = {
        "paper_id": f"10.1000/{number}",
        "title": f"  Useful   paper {number}  ",
        "summary": (f"A useful abstract for paper {number} with enough factual detail for reliable retrieval. " * 2).strip(),
        "authors": ["Ada Lovelace", " Ada Lovelace ", "Alan Turing"],
        "categories": ["Machine Learning", "machine learning", "RAG"],
        "primary_category": "Artificial Intelligence",
        "published": f"2025-01-{number:02d}",
        "updated": "",
        "abs_url": f"https://doi.org/10.1000/{number}",
        "pdf_url": "",
        "comment": "  accepted   paper ",
    }
    values.update(overrides)
    return PaperRecord(**values)


def test_raw_to_clean_contract_and_lineage() -> None:
    records = [
        paper(
            1,
            title="<b>Useful &amp; reliable</b> paper 1",
            summary=("<jats:p>A useful &amp; detailed abstract without markup for retrieval. </jats:p>" * 2),
        ),
        paper(2),
        paper(3, paper_id="10.1000/1"),
        paper(4, title=" "),
        paper(5, summary=""),
        paper(6, published="not-a-date"),
        paper(7, summary="Too short after cleaning."),
    ]

    clean = build_clean_dataframe(records, datetime(2025, 2, 1, tzinfo=UTC))

    assert clean.columns.tolist() == CLEAN_COLUMNS
    assert clean["paper_id"].tolist() == ["10.1000/2", "10.1000/1"]
    assert clean["paper_id"].is_unique
    assert clean.loc[1, "title"] == "Useful & reliable paper 1"
    assert "<" not in clean.loc[1, "summary"]
    assert "&amp;" not in clean.loc[1, "summary"]
    assert clean.loc[1, "authors"] == ["Ada Lovelace", "Alan Turing"]
    assert clean.loc[1, "categories"] == ["Artificial Intelligence", "Machine Learning", "RAG"]
    assert clean.loc[1, "age_days"] == 31
    assert clean.loc[1, "summary_chars"] == len(clean.loc[1, "summary"])
    assert clean.loc[1, "text_for_embedding"] == (
        f"Title: {clean.loc[1, 'title']} | Authors: {clean.loc[1, 'authors_joined']} "
        f"| Summary: {clean.loc[1, 'summary']}"
    )
    assert "Categories:" not in clean.loc[1, "text_for_embedding"]
    assert clean.attrs["cleaning_report"] == {
        "run_date": "2025-02-01T00:00:00+00:00",
        "input_records": 7,
        "valid_before_deduplication": 3,
        "output_records": 2,
        "filtered_records": 4,
        "duplicates_removed": 1,
        "rejected": {
            "missing_paper_id": 0,
            "missing_title": 1,
            "missing_summary": 1,
            "summary_too_short": 1,
            "invalid_published": 1,
        },
        "rules": {
            "required_fields": ["paper_id", "title", "summary", "published"],
            "minimum_summary_chars": 100,
            "duplicate_key": "paper_id (case-insensitive)",
        },
    }


def test_corruption_is_auditable_and_does_not_mutate_baseline(tmp_path) -> None:
    raw_records = [paper(number) for number in range(1, 13)]
    run_date = datetime(2025, 2, 1, tzinfo=UTC)
    baseline = build_clean_dataframe(raw_records, run_date)
    original = baseline.copy(deep=True)
    log_path = tmp_path / "corruption_log.json"

    corrupted = corrupt_clean_dataframe(baseline, log_path)
    log = json.loads(log_path.read_text(encoding="utf-8"))

    pd.testing.assert_frame_equal(baseline, original)
    assert [event["type"] for event in log["events"]] == [
        "drop_latest_records",
        "blank_summary",
        "inject_summary_noise",
        "truncate_title",
        "stale_published_date",
        "duplicate_rows",
    ]
    assert corrupted["paper_id"].duplicated().any()
    assert corrupted["summary"].eq("").any()
    assert corrupted["summary"].str.contains(NOISE_SUFFIX, regex=False).any()
    assert (corrupted["age_days"] > baseline["age_days"].max()).any()
    for _, row in corrupted.iterrows():
        assert row["text_for_embedding"].startswith(f"Title: {row['title']} | Authors:")
        assert row["text_for_embedding"].endswith(f"Summary: {row['summary']}".rstrip())
        assert "Categories:" not in row["text_for_embedding"]

    # Repair is a clean rebuild from the trusted raw snapshot, never an edit of
    # the corrupted dataframe.
    repaired = build_clean_dataframe(raw_records, run_date)
    pd.testing.assert_frame_equal(repaired, baseline)


def test_corruption_rejects_an_invalid_clean_contract(tmp_path) -> None:
    with pytest.raises(ValueError, match="missing clean columns"):
        corrupt_clean_dataframe(pd.DataFrame({"paper_id": ["one"]}), tmp_path / "log.json")


def test_clean_artifacts_round_trip_with_typed_json(tmp_path) -> None:
    clean = build_clean_dataframe([paper(1), paper(2)], datetime(2025, 2, 1, tzinfo=UTC))
    csv_path = tmp_path / "papers_clean.csv"
    json_path = tmp_path / "papers_clean.json"
    report_path = tmp_path / "cleaning_report.json"

    save_clean_dataframe(clean, csv_path, json_path)

    csv_frame = pd.read_csv(csv_path)
    json_records = json.loads(json_path.read_text(encoding="utf-8"))
    cleaning_report = json.loads(report_path.read_text(encoding="utf-8"))
    assert csv_frame.columns.tolist() == CLEAN_COLUMNS
    assert json.loads(csv_frame.loc[0, "authors"]) == ["Ada Lovelace", "Alan Turing"]
    assert json_records[0]["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert isinstance(json_records[0]["age_days"], int)
    assert all("\n" not in row["text_for_embedding"] for row in json_records)
    assert cleaning_report["input_records"] == 2
    assert cleaning_report["output_records"] == 2
    assert cleaning_report["filtered_records"] == 0


def test_corrupted_artifacts_round_trip_without_overwriting_lineage(tmp_path) -> None:
    baseline = build_clean_dataframe(
        [paper(number) for number in range(1, 13)], datetime(2025, 2, 1, tzinfo=UTC)
    )
    corrupted = corrupt_clean_dataframe(baseline, tmp_path / "corruption_log.json")
    csv_path = tmp_path / "corrupted.csv"
    json_path = tmp_path / "corrupted.json"

    save_dataframe_artifacts(corrupted, csv_path, json_path)

    assert len(pd.read_csv(csv_path, keep_default_na=False)) == len(corrupted)
    assert len(json.loads(json_path.read_text(encoding="utf-8"))) == len(corrupted)
    assert not (tmp_path / "cleaning_report.json").exists()


def test_save_requires_cleaning_lineage(tmp_path) -> None:
    clean = build_clean_dataframe([paper(1)], datetime(2025, 2, 1, tzinfo=UTC))
    clean.attrs.clear()

    with pytest.raises(ValueError, match="cleaning_report"):
        save_clean_dataframe(clean, tmp_path / "clean.csv", tmp_path / "clean.json")


def test_crossref_type_is_used_when_subject_is_missing() -> None:
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1000/fallback",
                    "title": ["Fallback category"],
                    "abstract": "A sufficiently detailed abstract.",
                    "type": "journal-article",
                    "published": {"date-parts": [[2025, 1, 1]]},
                }
            ]
        }
    }
    record = parse_crossref_payload(payload)[0]
    assert record.categories == ["journal-article"]
    assert record.primary_category == "journal-article"


def test_testset_rejects_nan_category_ground_truth(tmp_path) -> None:
    clean = build_clean_dataframe(
        [paper(number) for number in range(1, 13)], datetime(2025, 2, 1, tzinfo=UTC)
    )
    clean["categories_joined"] = pd.NA

    with pytest.raises(ValueError, match="ground truth is empty"):
        build_test_set(clean, tmp_path / "test_set.json")


def test_cp2_clean_testset_manifest_handoff() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    clean = pd.read_csv(project_dir / "data/clean/papers_clean.csv", keep_default_na=False)
    test_set = json.loads((project_dir / "data/eval/test_set.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (project_dir / "data/embeddings/papers_embeddings.json").read_text(encoding="utf-8")
    )

    result = validate_cp2_handoff(clean, test_set, manifest)
    assert result["status"] == "pass"
    assert result["clean_documents"] == result["manifest_documents"] == 24
    assert result["test_questions"] == 12


def test_cp5_corruption_artifacts_match_log_and_quality() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    settings = load_settings(project_dir)
    result = validate_cp5_corruption(
        pd.read_csv(settings.paths.clean_csv, keep_default_na=False),
        pd.read_csv(settings.paths.corrupted_clean_csv, keep_default_na=False),
        read_json(settings.paths.corruption_log),
        read_json(settings.paths.quality_dir / "corrupted_quality.json"),
        read_json(settings.paths.quality_dir / "corrupted_freshness_report.json"),
        settings,
    )
    assert result["status"] == "pass"
    assert result["baseline_rows"] == result["corrupted_rows"] == 24
    assert result["stale_rows"] == 3


def test_cp6_repair_artifacts_recover_baseline() -> None:
    project_dir = Path(__file__).resolve().parents[1]
    settings = load_settings(project_dir)
    quality_dir = settings.paths.quality_dir

    def frame(path):
        return pd.DataFrame(read_json(path), columns=CLEAN_COLUMNS)

    result = validate_cp6_repair(
        load_raw_records(settings.paths.raw_records_json),
        frame(settings.paths.clean_json),
        frame(settings.paths.corrupted_clean_json),
        frame(settings.paths.repaired_clean_json),
        read_json(settings.paths.clean_json.parent / "repaired_cleaning_report.json"),
        read_json(settings.paths.corruption_log),
        read_json(quality_dir / "baseline_quality.json"),
        read_json(quality_dir / "corrupted_quality.json"),
        read_json(quality_dir / "repaired_quality.json"),
        read_json(settings.paths.freshness_report),
        read_json(quality_dir / "corrupted_freshness_report.json"),
        read_json(quality_dir / "repaired_freshness_report.json"),
        read_json(settings.paths.baseline_metrics),
        read_json(settings.paths.corrupted_metrics),
        read_json(settings.paths.repaired_metrics),
        read_json(settings.paths.embeddings_json),
        read_json(settings.paths.repaired_embeddings_json),
    )
    assert result["status"] == "pass"
    assert result["repaired_equals_baseline"] is True
