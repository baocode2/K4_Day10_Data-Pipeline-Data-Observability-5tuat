from __future__ import annotations

"""Role 2 (ingest owner, Nhom 5) - Checkpoint 1 checks.

CP1 goal for this role is verification, not new code: cross-check the raw
Crossref snapshot against the parsed PaperRecord list, and confirm every
record has the fields the cleaning owner needs before handoff.

Run: pytest tests/test_role2_cp1_raw_lineage.py -v
"""

import json

import pytest

from core.config import load_settings
from core.utils import safe_slug
from ingestion.crossref import parse_crossref_payload

SETTINGS = load_settings()
RAW_RESPONSE_PATH = SETTINGS.paths.raw_api_response
RAW_RECORDS_PATH = SETTINGS.paths.raw_records_json


def _require_raw_artifacts() -> None:
    if not RAW_RESPONSE_PATH.exists() or not RAW_RECORDS_PATH.exists():
        pytest.fail(
            "Raw artifacts missing. CP0 (fetch_source_records) must run before CP1: "
            f"expected {RAW_RESPONSE_PATH} and {RAW_RECORDS_PATH}."
        )


def test_raw_response_reparses_into_the_committed_records_snapshot() -> None:
    """crossref_records.json must be derivable from crossref_response.json, not hand-edited."""
    _require_raw_artifacts()
    raw_response = json.loads(RAW_RESPONSE_PATH.read_text(encoding="utf-8"))
    committed_records = json.loads(RAW_RECORDS_PATH.read_text(encoding="utf-8"))

    reparsed_ids = {record.paper_id for record in parse_crossref_payload(raw_response)}
    committed_ids = {record["paper_id"] for record in committed_records}

    assert reparsed_ids == committed_ids, (
        "crossref_records.json has drifted from crossref_response.json -- "
        "regenerate it via parse_crossref_payload instead of editing records by hand."
    )


def test_every_committed_record_has_the_fields_cleaning_needs() -> None:
    """Cleaning owner should never have to guess a missing field."""
    _require_raw_artifacts()
    records = json.loads(RAW_RECORDS_PATH.read_text(encoding="utf-8"))
    assert records, "No parsed records to hand off to the cleaning owner."

    for record in records:
        assert record["paper_id"], f"missing paper_id: {record}"
        assert record["title"].strip(), f"missing title: {record['paper_id']}"
        assert record["summary"].strip(), f"missing summary: {record['paper_id']}"
        assert isinstance(record["authors"], list), f"authors must be a list: {record['paper_id']}"
        assert isinstance(record["categories"], list), f"categories must be a list: {record['paper_id']}"
        assert record["published"], f"missing published date: {record['paper_id']}"
        assert record["abs_url"], f"missing abs_url: {record['paper_id']}"


def test_paper_id_is_a_stable_doi_slug_and_unique() -> None:
    _require_raw_artifacts()
    records = json.loads(RAW_RECORDS_PATH.read_text(encoding="utf-8"))
    ids = [record["paper_id"] for record in records]

    assert len(ids) == len(set(ids)), "Duplicate paper_id in raw records -- DOI-based ID is not stable."
    for paper_id in ids:
        assert paper_id == safe_slug(paper_id), (
            f"paper_id {paper_id!r} is not already a safe_slug output; "
            "re-check the DOI -> paper_id mapping in parse_crossref_payload."
        )


def test_parse_crossref_payload_rejects_records_missing_title_or_abstract() -> None:
    """Deterministic guard, independent of whatever Crossref happens to return today."""
    payload = {
        "message": {
            "items": [
                {
                    "DOI": "10.1000/valid",
                    "title": ["A valid paper with title"],
                    "abstract": "<jats:p>A sufficiently long abstract for testing.</jats:p>",
                    "author": [{"given": "Ada", "family": "Lovelace"}],
                    "subject": ["Machine Learning"],
                    "published": {"date-parts": [[2024, 5, 1]]},
                    "URL": "https://doi.org/10.1000/valid",
                },
                {"DOI": "10.1000/no-title", "abstract": "Has abstract but no title"},
                {"DOI": "10.1000/no-abstract", "title": ["Has title but no abstract"]},
                {"title": ["No DOI at all"], "abstract": "Has abstract but no DOI"},
            ]
        }
    }

    records = parse_crossref_payload(payload)

    assert [record.paper_id for record in records] == [safe_slug("10.1000/valid")]
    assert records[0].title == "A valid paper with title"
    assert "<" not in records[0].summary
    assert records[0].authors == ["Ada Lovelace"]
    assert records[0].published == "2024-05-01"