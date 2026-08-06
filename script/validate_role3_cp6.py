"""Validate Role 3 CP6 repair lineage and recovery evidence."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from ingestion.cleaning import CLEAN_COLUMNS
from ingestion.cp6_validation import validate_cp6_repair
from ingestion.crossref import load_raw_records


def _frame(path: Path) -> pd.DataFrame:
    return pd.DataFrame(read_json(path), columns=CLEAN_COLUMNS)


def main() -> None:
    settings = load_settings()
    quality_dir = settings.paths.quality_dir
    result = validate_cp6_repair(
        raw_records=load_raw_records(settings.paths.raw_records_json),
        baseline=_frame(settings.paths.clean_json),
        corrupted=_frame(settings.paths.corrupted_clean_json),
        repaired=_frame(settings.paths.repaired_clean_json),
        repaired_cleaning_report=read_json(settings.paths.clean_json.parent / "repaired_cleaning_report.json"),
        corruption_log=read_json(settings.paths.corruption_log),
        baseline_quality=read_json(quality_dir / "baseline_quality.json"),
        corrupted_quality=read_json(quality_dir / "corrupted_quality.json"),
        repaired_quality=read_json(quality_dir / "repaired_quality.json"),
        baseline_freshness=read_json(settings.paths.freshness_report),
        corrupted_freshness=read_json(quality_dir / "corrupted_freshness_report.json"),
        repaired_freshness=read_json(quality_dir / "repaired_freshness_report.json"),
        baseline_metrics=read_json(settings.paths.baseline_metrics),
        corrupted_metrics=read_json(settings.paths.corrupted_metrics),
        repaired_metrics=read_json(settings.paths.repaired_metrics),
        baseline_manifest=read_json(settings.paths.embeddings_json),
        repaired_manifest=read_json(settings.paths.repaired_embeddings_json),
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
