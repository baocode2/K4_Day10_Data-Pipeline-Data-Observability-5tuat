from __future__ import annotations

"""Role 2 (ingest owner, Nhom 5) - Checkpoint 6 checks.

CP6 goal: reload raw records from the exact snapshot used at baseline, prove
a corrupted/dropped record comes back correctly once cleaning is re-run from
that raw snapshot, and help confirm no API key or secret leaked into a
committed artifact.

Run: pytest tests/test_role2_cp6_repair_lineage_and_secrets.py -v
"""

import json
import re
import tempfile
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

import pytest

from core.config import load_settings
from core.utils import write_json
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import PaperRecord, load_raw_records

SETTINGS = load_settings()
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


def test_reload_raw_records_reproduces_the_exact_baseline_snapshot(tmp_path: Path) -> None:
    """CP6: 'Reload raw records dung snapshot/source dung o baseline.'"""
    original = [paper(number) for number in range(1, 6)]
    snapshot_path = tmp_path / "crossref_records.json"
    write_json(snapshot_path, [asdict(record) for record in original])

    reloaded = load_raw_records(snapshot_path)

    assert reloaded == original


def test_repaired_record_matches_raw_source_after_being_dropped() -> None:
    """CP6: 'Chung minh record corrupt/drop da phuc hoi bang lineage/source evidence.'"""
    raw_records = [paper(number) for number in range(1, 13)]
    raw_by_id = {record.paper_id: record for record in raw_records}

    baseline = build_clean_dataframe(raw_records, RUN_DATE)
    with tempfile.TemporaryDirectory() as tmp:
        log_path = Path(tmp) / "corruption_log.json"
        corrupted = corrupt_clean_dataframe(baseline, log_path)
        log = json.loads(log_path.read_text(encoding="utf-8"))

    dropped_id = next(event for event in log["events"] if event["type"] == "drop_latest_records")["record_ids"][0]
    assert dropped_id not in set(corrupted["paper_id"]), "Setup issue: sample id was not actually dropped."

    # Repair == rebuild from the raw snapshot, never patch `corrupted` in place.
    repaired = build_clean_dataframe(raw_records, RUN_DATE)
    repaired_row = repaired[repaired["paper_id"] == dropped_id].iloc[0]
    raw_source = raw_by_id[dropped_id]

    assert repaired_row["title"] == " ".join(raw_source.title.split())
    assert repaired_row["abs_url"] == raw_source.abs_url


def test_dotenv_is_git_ignored() -> None:
    gitignore_path = SETTINGS.paths.project_dir / ".gitignore"
    gitignore = gitignore_path.read_text(encoding="utf-8")
    assert ".env" in gitignore.splitlines(), ".env must stay in .gitignore so provider API keys never get committed."


_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{16,}"),
]


def test_raw_response_artifact_has_no_obvious_leaked_api_key() -> None:
    if not SETTINGS.paths.raw_api_response.exists():
        pytest.skip("No raw response artifact to scan yet.")
    text = SETTINGS.paths.raw_api_response.read_text(encoding="utf-8")
    for pattern in _SECRET_PATTERNS:
        assert not pattern.search(text), f"Possible leaked credential in {SETTINGS.paths.raw_api_response}"