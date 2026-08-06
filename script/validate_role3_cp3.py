"""Validate Role 3's clean schema and observability evidence at CP3."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd

from core.config import load_settings
from core.utils import read_json
from ingestion.cp3_validation import validate_cp3_clean_quality


def main() -> None:
    settings = load_settings()
    result = validate_cp3_clean_quality(
        clean_df=pd.read_csv(settings.paths.clean_csv, keep_default_na=False),
        cleaning_report=read_json(settings.paths.clean_json.with_name("cleaning_report.json")),
        quality=read_json(settings.paths.quality_dir / "baseline_quality.json"),
        freshness=read_json(settings.paths.freshness_report),
        settings=settings,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
