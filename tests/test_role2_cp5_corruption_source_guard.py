from __future__ import annotations

"""Role 2 (ingest owner, Nhom 5) - Checkpoint 5 checks.

CP5 goal: confirm the raw source is untouched before corruption runs, be able
to point at one corrupted/dropped record with a clear lineage trail, and make
sure the corruption flow never fetches a fresh source (which would make the
before/after comparison unfair).

Uses synthetic PaperRecord fixtures so these checks are deterministic and do
not depend on whatever the live Crossref query happens to return today.

Run: pytest tests/test_role2_cp5_corruption_source_guard.py -v
"""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest
import requests

from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import PaperRecord

RUN_DATE = datetime(2025, 2, 1, tzinfo=UTC)


def paper(number: int, **overrides) -> PaperRecord:
    values = {
        "paper_id": f"10.1000/{number}",
        "title": f"Paper {number} about retrieval augmented generation",
        "summary": (
            f"A sufficiently long abstract for paper {number} covering methodology and results. " * 2
        ).strip(),
        "authors": ["Ada Lovelace"],
        "categories": ["Machine Learning"],
        "primary_category": "Machine Learning",
        "published": f"2025-01-{number:02d}",
        "updated": "",
        "abs_url": f"https://doi.org/10.1000/{number}",
        "pdf_url": f"https://example.org/{number}.pdf",
        "comment": "",
    }
    values.update(overrides)
    return PaperRecord(**values)


def _run_corruption(raw_records: list[PaperRecord]) -> tuple[dict, pd.DataFrame]:
    baseline = build_clean_dataframe(raw_records, RUN_DATE)
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "corruption_log.json"
        corrupted = corrupt_clean_dataframe(baseline, log_path)
        log = json.loads(log_path.read_text(encoding="utf-8"))
    return log, corrupted


def test_raw_records_are_not_mutated_by_the_corruption_flow() -> None:
    raw_records = [paper(number) for number in range(1, 13)]
    frozen_raw = list(raw_records)  # PaperRecord is a frozen dataclass; corrupt_clean_dataframe never sees it.

    _run_corruption(raw_records)

    assert raw_records == frozen_raw, "corrupt_clean_dataframe must never touch the raw record list."


def test_corruption_flow_runs_without_any_network_call(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Corruption must reuse the frozen raw snapshot, not fetch a new one.")

    monkeypatch.setattr(requests, "get", _fail_if_called)

    raw_records = [paper(number) for number in range(1, 13)]
    log, _ = _run_corruption(raw_records)

    assert log["events"], "Corruption should log at least one event."


def test_can_pick_a_dropped_record_with_a_clear_lineage_trail() -> None:
    """CP5: 'chon record co lineage ro de chung minh co the repair'."""
    raw_records = [paper(number) for number in range(1, 13)]
    raw_by_id = {record.paper_id: record for record in raw_records}

    log, corrupted = _run_corruption(raw_records)

    dropped_event = next(event for event in log["events"] if event["type"] == "drop_latest_records")
    assert dropped_event["record_ids"], "No dropped record to demonstrate repair with."

    sample_id = dropped_event["record_ids"][0]
    assert sample_id not in set(corrupted["paper_id"]), "Sample id should actually be missing from corrupted data."
    assert sample_id in raw_by_id, "Dropped paper_id must still be traceable in the raw snapshot."

    raw_source = raw_by_id[sample_id]
    assert raw_source.title and raw_source.abs_url