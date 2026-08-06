"""Validate Role 3's CP2 handoff against real baseline artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import chromadb
import pandas as pd

from core.config import load_settings
from core.utils import read_json
from ingestion.cp2_validation import validate_cp2_handoff


def main() -> None:
    settings = load_settings()
    clean = pd.read_csv(settings.paths.clean_csv, keep_default_na=False)
    test_set = read_json(settings.paths.eval_testset)
    manifest = read_json(settings.paths.embeddings_json)
    result = validate_cp2_handoff(clean, test_set, manifest)

    client = chromadb.PersistentClient(path=str(settings.paths.chroma_dir))
    collection_name = str(manifest["collection_name"])
    try:
        collection = client.get_collection(collection_name)
    except Exception as exc:
        raise RuntimeError(
            f"CP2 validation failed: Chroma collection {collection_name!r} does not exist."
        ) from exc
    collection_count = collection.count()
    if collection_count != len(clean):
        raise RuntimeError(
            f"CP2 validation failed: Chroma has {collection_count} docs; clean has {len(clean)}."
        )
    result["chroma_collection"] = collection_name
    result["chroma_documents"] = collection_count
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
