"""Validate existing Role 3 CP5 artifacts without changing them."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from ingestion.cp5_validation import validate_cp5_corruption


def main() -> None:
    settings = load_settings()
    result = validate_cp5_corruption(
        pd.read_csv(settings.paths.clean_csv, keep_default_na=False),
        pd.read_csv(settings.paths.corrupted_clean_csv, keep_default_na=False),
        read_json(settings.paths.corruption_log),
        read_json(settings.paths.quality_dir / "corrupted_quality.json"),
        read_json(settings.paths.quality_dir / "corrupted_freshness_report.json"),
        settings,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
