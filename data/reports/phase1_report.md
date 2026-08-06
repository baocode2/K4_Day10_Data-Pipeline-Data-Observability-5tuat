# Phase 1 - Baseline report

## Source

- source_api: Crossref REST API
- query: agentic retrieval augmented generation large language model
- filter: from-pub-date:2026-02-07,has-abstract:true
- raw_records: 24
- clean_records: 24
- collection_name: papers-baseline

## Evaluation metrics

| Metric | Value |
| --- | --- |
| samples | 12.0000 |
| retrieval_hit_rate | 1.0000 |
| mean_token_f1 | 1.0000 |
| judge_accuracy | 1.0000 |
| mean_judge_score | 5.0000 |
| ragas | skipped=Set RUN_RAGAS=1 to enable the slower Ragas pass. |

## Data quality

- Overall: **PASS** (total_rows = 24)

| Check | Status | Message |
| --- | --- | --- |
| row_count | PASS | dataset has 24 rows |
| paper_id_unique | PASS | paper_id nulls=0, duplicates=0 |
| title_not_null | PASS | rows with missing title = 0 |
| summary_min_chars | PASS | rows with summary < 50 chars = 0 |
| text_for_embedding_not_empty | PASS | rows with empty text_for_embedding = 0 |
| age_days_valid | PASS | rows with invalid age_days = 0 |
| freshness_threshold | PASS | rows older than 180 days = 0 |

## Freshness

- Total rows: 24
- Latest published: 2026-08-01T00:00:00+00:00
- Oldest published: 2026-02-12T00:00:00+00:00
- Threshold days: 180
- Stale rows: 0
- Is fresh: **PASS**
