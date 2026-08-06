from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json


MIN_DOCS = 4
PER_TYPE = 3
QUESTION_TYPES = ("summary", "authors", "date", "categories")


def _summary_question(row: pd.Series) -> dict[str, Any]:
    return {
        "question_type": "summary",
        "question": f"What is the main idea of '{row['title']}'?",
        "ground_truth": first_sentence(str(row.get("summary", ""))),
    }


def _authors_question(row: pd.Series) -> dict[str, Any]:
    return {
        "question_type": "authors",
        "question": f"Who authored '{row['title']}'?",
        "ground_truth": str(row.get("authors_joined", "")),
    }


def _date_question(row: pd.Series) -> dict[str, Any]:
    return {
        "question_type": "date",
        "question": f"When was '{row['title']}' published?",
        "ground_truth": str(row.get("published", "")),
    }


def _categories_question(row: pd.Series) -> dict[str, Any]:
    return {
        "question_type": "categories",
        "question": f"What categories does '{row['title']}' belong to?",
        "ground_truth": str(row.get("categories_joined", "")),
    }


_QUESTION_BUILDERS = {
    "summary": _summary_question,
    "authors": _authors_question,
    "date": _date_question,
    "categories": _categories_question,
}


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    if len(df) < MIN_DOCS:
        raise ValueError(f"Need at least {MIN_DOCS} cleaned docs to build a test set, got {len(df)}.")

    rows = df.head(PER_TYPE).reset_index(drop=True)
    test_set: list[dict[str, Any]] = []
    sample_id = 0
    for question_type in QUESTION_TYPES:
        builder = _QUESTION_BUILDERS[question_type]
        for _, row in rows.iterrows():
            sample_id += 1
            payload = builder(row)
            paper_id = str(row["paper_id"])
            test_set.append(
                {
                    "id": f"q{sample_id:03d}",
                    "question_type": payload["question_type"],
                    "question": payload["question"],
                    "ground_truth": payload["ground_truth"],
                    "ground_truth_doc_ids": [paper_id],
                }
            )
    write_json(output_path, test_set)
    return test_set