from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import write_json


MIN_DOCS = 12
PER_TYPE = 3
QUESTION_TYPES = ("summary", "authors", "date", "categories")


def _cell_text(row: pd.Series, column: str) -> str:
    value = row.get(column, "")
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _summary_question(row: pd.Series) -> dict[str, Any]:
    return {
        "question_type": "summary",
        "question": f"What is the main idea of '{row['title']}'?",
        "ground_truth": _cell_text(row, "summary"),
    }


def _authors_question(row: pd.Series) -> dict[str, Any]:
    return {
        "question_type": "authors",
        "question": f"Who authored '{row['title']}'?",
        "ground_truth": _cell_text(row, "authors_joined"),
    }


def _date_question(row: pd.Series) -> dict[str, Any]:
    return {
        "question_type": "date",
        "question": f"When was '{row['title']}' published?",
        "ground_truth": _cell_text(row, "published"),
    }


def _categories_question(row: pd.Series) -> dict[str, Any]:
    return {
        "question_type": "categories",
        "question": f"What categories does '{row['title']}' belong to?",
        "ground_truth": _cell_text(row, "categories_joined"),
    }


_QUESTION_BUILDERS = {
    "summary": _summary_question,
    "authors": _authors_question,
    "date": _date_question,
    "categories": _categories_question,
}


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    total_needed = PER_TYPE * len(QUESTION_TYPES)
    if len(df) < total_needed:
        raise ValueError(
            f"Need at least {total_needed} cleaned docs to build a test set, got {len(df)}."
        )

    sampled = df.head(total_needed).reset_index(drop=True)
    test_set: list[dict[str, Any]] = []
    sample_id = 0
    for type_offset, question_type in enumerate(QUESTION_TYPES):
        builder = _QUESTION_BUILDERS[question_type]
        slice_start = type_offset * PER_TYPE
        for _, row in sampled.iloc[slice_start : slice_start + PER_TYPE].iterrows():
            sample_id += 1
            payload = builder(row)
            paper_id = str(row["paper_id"])
            if not payload["ground_truth"]:
                raise ValueError(
                    f"Cannot build {question_type} question for {paper_id}: ground truth is empty."
                )
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
