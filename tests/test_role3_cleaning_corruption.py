from __future__ import annotations

from datetime import UTC, datetime
import json

import pandas as pd
import pytest

from ingestion.cleaning import CLEAN_COLUMNS, build_clean_dataframe, save_clean_dataframe
from ingestion.corruption import NOISE_SUFFIX, corrupt_clean_dataframe
from ingestion.crossref import PaperRecord


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
        "input_records": 7,
        "valid_before_deduplication": 3,
        "output_records": 2,
        "duplicates_removed": 1,
        "rejected": {
            "missing_paper_id": 0,
            "missing_title": 1,
            "missing_summary": 1,
            "summary_too_short": 1,
            "invalid_published": 1,
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

    save_clean_dataframe(clean, csv_path, json_path)

    csv_frame = pd.read_csv(csv_path)
    json_records = json.loads(json_path.read_text(encoding="utf-8"))
    assert csv_frame.columns.tolist() == CLEAN_COLUMNS
    assert json.loads(csv_frame.loc[0, "authors"]) == ["Ada Lovelace", "Alan Turing"]
    assert json_records[0]["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert isinstance(json_records[0]["age_days"], int)
    assert all("\n" not in row["text_for_embedding"] for row in json_records)
