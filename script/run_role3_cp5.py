"""Create and validate Role 3's controlled CP5 corruption artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from ingestion.cleaning import save_dataframe_artifacts
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.cp5_validation import validate_cp5_corruption
from observability.quality import build_freshness_report, run_data_quality_checks


def main() -> None:
    settings = load_settings()
    baseline = pd.read_csv(settings.paths.clean_csv, keep_default_na=False)
    baseline_snapshot = baseline.copy(deep=True)
    corrupted = corrupt_clean_dataframe(baseline, settings.paths.corruption_log)
    save_dataframe_artifacts(
        corrupted,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )
    quality = run_data_quality_checks(corrupted, settings, "corrupted")
    freshness_path = settings.paths.quality_dir / "corrupted_freshness_report.json"
    freshness = build_freshness_report(corrupted, settings, freshness_path)
    pd.testing.assert_frame_equal(baseline, baseline_snapshot)
    result = validate_cp5_corruption(
        baseline,
        corrupted,
        read_json(settings.paths.corruption_log),
        quality,
        freshness,
        settings,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
