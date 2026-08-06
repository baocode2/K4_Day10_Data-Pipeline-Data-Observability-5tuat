"""
Build CP2 baseline embedding index for Role 4.
Reads data/clean/papers_clean.csv and creates data/embeddings/papers_embeddings.json & Chroma collection 'papers-baseline'.
"""
from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
from core.config import load_settings
from retrieval.index import LocalEmbeddingIndex


def main() -> None:
    settings = load_settings()
    clean_path = settings.paths.clean_csv
    if not clean_path.exists():
        print(f"❌ Error: {clean_path} does not exist. Role 3 clean data is required.")
        sys.exit(1)

    print(f"📖 Reading clean data from {clean_path}...")
    df = pd.read_csv(clean_path)
    print(f"  Rows loaded: {len(df)}")

    print("🔨 Building LocalEmbeddingIndex (papers-baseline)...")
    index = LocalEmbeddingIndex.build(df, settings)

    print(f"✅ Baseline index built successfully!")
    print(f"  Manifest: {settings.paths.embeddings_json}")
    print(f"  Collection: {index.collection_name}")
    print(f"  Documents indexed: {len(index.documents)}")


if __name__ == "__main__":
    main()
