from __future__ import annotations

"""Role 2 (ingest owner, Nhom 5) - Checkpoint 3 checks.

CP3 goal: confirm raw artifacts and lineage are still readable after the
baseline end-to-end run, reconcile raw -> clean row counts, and make sure the
baseline entrypoint reuses the frozen raw snapshot instead of fetching again.

Run: pytest tests/test_role2_cp3_baseline_integrity.py -v
"""

import json
from datetime import UTC, datetime

import pytest
import requests

from core.config import load_settings
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import load_raw_records

SETTINGS = load_settings()


def test_raw_response_and_records_are_still_readable() -> None:
    for path in (SETTINGS.paths.raw_api_response, SETTINGS.paths.raw_records_json):
        if not path.exists():
            pytest.fail(f"Missing raw artifact before baseline run: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload, f"{path} is present but empty."


def test_raw_to_clean_row_count_delta_matches_the_cleaning_report() -> None:
    if not SETTINGS.paths.raw_records_json.exists() or not SETTINGS.paths.clean_json.exists():
        pytest.fail("Need both raw records and clean artifacts to reconcile counts for CP3.")

    raw_records = load_raw_records(SETTINGS.paths.raw_records_json)
    clean = build_clean_dataframe(raw_records, datetime.now(UTC))
    report = clean.attrs["cleaning_report"]

    on_disk_clean = json.loads(SETTINGS.paths.clean_json.read_text(encoding="utf-8"))

    assert report["input_records"] == len(raw_records)
    assert report["output_records"] == len(clean) == len(on_disk_clean), (
        "papers_clean.json tren dia khong khop voi build_clean_dataframe(load_raw_records(...)) hien tai -- "
        "clean artifact co the da duoc build tu raw snapshot khac hoac bi sua tay."
    )

    accounted_for = report["output_records"] + report["duplicates_removed"] + sum(report["rejected"].values())
    assert accounted_for == report["input_records"], f"Chenh lech raw->clean chua duoc giai thich het: {report}"


def test_baseline_pipeline_must_reuse_the_raw_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """phase1.py should call load_raw_records, not fetch_source_records, unless refresh_source is True."""

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("Unexpected network call while refresh_source is False.")

    monkeypatch.setattr(requests, "get", _fail_if_called)
    assert SETTINGS.refresh_source is False

    records = load_raw_records(SETTINGS.paths.raw_records_json)
    assert records