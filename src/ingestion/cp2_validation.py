from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence


INVALID_TEXT_VALUES = {"", "nan", "none", "null"}
TEST_SET_FIELDS = {
    "id",
    "question_type",
    "question",
    "ground_truth",
    "ground_truth_doc_ids",
}
MANIFEST_METADATA_FIELDS = {
    "paper_id",
    "title",
    "published",
    "authors_joined",
    "categories_joined",
    "summary",
    "abs_url",
    "pdf_url",
}


def _text(value: Any) -> str:
    if value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        return ""
    return str(value).strip()


def _expected_ground_truth(question_type: str, row: pd.Series) -> str:
    field_map = {
        "authors": "authors_joined",
        "date": "published",
        "categories": "categories_joined",
    }
    if question_type == "summary":
        return first_sentence(_text(row.get("summary")))
    if question_type not in field_map:
        raise ValueError(f"Unsupported question_type in CP2 test set: {question_type}")
    return _text(row.get(field_map[question_type]))


def validate_cp2_handoff(
    clean_df: pd.DataFrame,
    test_set: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Validate Role 3's clean handoff to evaluation and retrieval."""
    if clean_df.empty:
        raise ValueError("CP2 validation failed: clean dataset is empty.")
    clean_ids = clean_df["paper_id"].map(_text)
    if clean_ids.eq("").any() or clean_ids.str.casefold().duplicated().any():
        raise ValueError("CP2 validation failed: clean paper_id values are blank or duplicated.")
    if clean_df["text_for_embedding"].map(_text).isin(INVALID_TEXT_VALUES).any():
        raise ValueError("CP2 validation failed: text_for_embedding contains blank/invalid values.")

    clean_by_id = {
        _text(row["paper_id"]): row for _, row in clean_df.iterrows()
    }
    question_ids: set[str] = set()
    for item in test_set:
        missing = TEST_SET_FIELDS.difference(item)
        if missing:
            raise ValueError(f"CP2 validation failed: test-set item is missing {sorted(missing)}.")
        question_id = _text(item["id"])
        if not question_id or question_id in question_ids:
            raise ValueError(f"CP2 validation failed: duplicate/blank question ID {question_id!r}.")
        question_ids.add(question_id)

        truth = _text(item["ground_truth"])
        if truth.casefold() in INVALID_TEXT_VALUES:
            raise ValueError(f"CP2 validation failed: {question_id} has invalid ground truth {truth!r}.")
        doc_ids = item["ground_truth_doc_ids"]
        if not isinstance(doc_ids, list) or len(doc_ids) != 1 or _text(doc_ids[0]) not in clean_by_id:
            raise ValueError(f"CP2 validation failed: {question_id} has invalid ground_truth_doc_ids.")
        source_row = clean_by_id[_text(doc_ids[0])]
        expected = _expected_ground_truth(_text(item["question_type"]), source_row)
        if truth != expected:
            raise ValueError(
                f"CP2 validation failed: {question_id} ground truth does not match clean data."
            )

    documents = manifest.get("documents")
    if not isinstance(documents, list) or len(documents) != len(clean_df):
        raise ValueError("CP2 validation failed: embedding manifest count differs from clean row count.")
    manifest_by_id: dict[str, dict[str, Any]] = {}
    for document in documents:
        paper_id = _text(document.get("paper_id"))
        metadata = document.get("metadata", {})
        if not paper_id or paper_id in manifest_by_id:
            raise ValueError("CP2 validation failed: manifest paper IDs are blank or duplicated.")
        if paper_id not in clean_by_id:
            raise ValueError(f"CP2 validation failed: manifest paper ID {paper_id} is not in clean data.")
        if MANIFEST_METADATA_FIELDS.difference(metadata):
            raise ValueError(f"CP2 validation failed: manifest metadata is incomplete for {paper_id}.")
        if _text(document.get("content")) != _text(clean_by_id[paper_id]["text_for_embedding"]):
            raise ValueError(f"CP2 validation failed: manifest content differs for {paper_id}.")
        if _text(metadata.get("categories_joined")).casefold() in INVALID_TEXT_VALUES:
            raise ValueError(f"CP2 validation failed: manifest category is invalid for {paper_id}.")
        manifest_by_id[paper_id] = document
    if set(manifest_by_id) != set(clean_by_id):
        raise ValueError("CP2 validation failed: manifest and clean paper IDs differ.")

    return {
        "clean_documents": len(clean_df),
        "test_questions": len(test_set),
        "manifest_documents": len(documents),
        "question_types": sorted({_text(item["question_type"]) for item in test_set}),
        "status": "pass",
    }
