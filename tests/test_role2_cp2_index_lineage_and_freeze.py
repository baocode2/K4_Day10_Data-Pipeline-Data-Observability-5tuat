from __future__ import annotations

"""Role 2 (ingest owner, Nhom 5) - Checkpoint 2 checks.

CP2 goal: trace one paper_id through raw -> clean -> index metadata, be ready
to produce source evidence when an answer looks wrong, and make sure nothing
in this checkpoint quietly re-fetches the source (which would change the
baseline out from under the rest of the team).

Run: pytest tests/test_role2_cp2_index_lineage_and_freeze.py -v
"""

import json

import pytest
import requests

from core.config import load_settings
from ingestion.crossref import load_raw_records

SETTINGS = load_settings()


def _load_json_if_exists(path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _require_raw_and_clean():
    raw = _load_json_if_exists(SETTINGS.paths.raw_records_json)
    clean = _load_json_if_exists(SETTINGS.paths.clean_json)
    if raw is None or clean is None:
        pytest.fail(
            "Need both raw and clean snapshots for CP2 lineage checks: "
            f"{SETTINGS.paths.raw_records_json}, {SETTINGS.paths.clean_json}"
        )
    return raw, clean


def test_a_sample_paper_id_is_consistent_between_raw_and_clean() -> None:
    raw, clean = _require_raw_and_clean()
    raw_by_id = {row["paper_id"]: row for row in raw}
    clean_by_id = {row["paper_id"]: row for row in clean}

    shared_ids = raw_by_id.keys() & clean_by_id.keys()
    assert shared_ids, "No paper_id survived cleaning -- nothing to trace end-to-end."

    sample_id = sorted(shared_ids)[0]
    raw_row, clean_row = raw_by_id[sample_id], clean_by_id[sample_id]

    assert clean_row["title"].strip() == " ".join(raw_row["title"].split())
    assert clean_row["abs_url"] == raw_row["abs_url"]
    assert clean_row["pdf_url"] == raw_row["pdf_url"]


def test_a_sample_paper_id_is_consistent_with_index_metadata_once_built() -> None:
    _, clean = _require_raw_and_clean()
    manifest = _load_json_if_exists(SETTINGS.paths.embeddings_json)
    if manifest is None:
        pytest.skip(
            "papers-baseline chua duoc build (data/embeddings/papers_embeddings.json khong co). "
            "Chay lai sau khi role rag build xong index."
        )

    clean_by_id = {row["paper_id"]: row for row in clean}
    documents = manifest["documents"]
    assert documents, "Embedding manifest has no documents."

    sample_doc = documents[0]
    metadata = sample_doc["metadata"]
    clean_row = clean_by_id[metadata["paper_id"]]

    assert metadata["title"] == clean_row["title"]
    assert metadata["abs_url"] == clean_row["abs_url"]
    assert metadata["pdf_url"] == clean_row["pdf_url"]
    assert metadata["published"] == clean_row["published"]


def test_source_evidence_bundle_is_enough_to_dispute_a_wrong_answer() -> None:
    """What to attach to a bug report when the evaluator/agent gets a question wrong."""
    _, clean = _require_raw_and_clean()
    clean_row = clean[0]

    evidence = {
        "paper_id": clean_row["paper_id"],
        "title": clean_row["title"],
        "abs_url": clean_row["abs_url"],
        "summary_excerpt": clean_row["summary"][:200],
    }

    assert evidence["paper_id"]
    assert evidence["title"]
    assert evidence["abs_url"].startswith("http"), "abs_url phai tro duoc toi nguon Crossref that."
    assert evidence["summary_excerpt"]


def test_load_raw_records_never_calls_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard against accidentally re-fetching the source mid-checkpoint."""

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("load_raw_records must not perform network I/O.")

    monkeypatch.setattr(requests, "get", _fail_if_called)

    if not SETTINGS.paths.raw_records_json.exists():
        pytest.fail(f"Missing snapshot: {SETTINGS.paths.raw_records_json}")

    records = load_raw_records(SETTINGS.paths.raw_records_json)
    assert records


def test_refresh_source_is_off_unless_explicitly_requested() -> None:
    assert SETTINGS.refresh_source is False, (
        "REFRESH_SOURCE dang bat -- baseline artifacts co the khong con khop voi raw snapshot da freeze. "
        "Tat no cho toi khi ca team chu dong lam lai baseline."
    )