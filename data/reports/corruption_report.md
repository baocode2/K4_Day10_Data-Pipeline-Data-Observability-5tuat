# Corruption - Repair comparison report

## Metrics comparison

| Metric | Baseline | Corrupted | Repaired | Δ (Corrupt-Base) | Δ (Repair-Corrupt) |
| --- | --- | --- | --- | --- | --- |
| samples | 12.0000 | 12.0000 | 12.0000 | +0.0000 | +0.0000 |
| retrieval_hit_rate | 1.0000 | 0.7500 | 1.0000 | -0.2500 | +0.2500 |
| mean_token_f1 | 0.8219 | 0.7736 | 0.8219 | -0.0484 | +0.0484 |
| judge_accuracy | 0.7500 | 0.7500 | 0.7500 | +0.0000 | +0.0000 |
| mean_judge_score | 4.2500 | 4.1667 | 4.2500 | -0.0833 | +0.0833 |

## Quality comparison

| Stage | Overall | Total rows |
| --- | --- | --- |
| baseline | n/a | n/a |
| corrupted | FAIL | 24 |
| repaired | PASS | 24 |

## Freshness comparison

| Stage | Is fresh | Stale rows | Latest published |
| --- | --- | --- | --- |
| baseline | n/a | n/a | n/a |
| corrupted | FAIL | 3 | 2026-07-03T00:00:00+00:00 |
| repaired | PASS | 0 | 2026-08-01T00:00:00+00:00 |
