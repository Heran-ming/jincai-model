# Jincai observation dataset

This folder stores structured rows extracted from locked prediction reports and later reviews.

The goal is to make blind replay, market-type hit rate, and 1u return analysis reproducible without re-parsing free-form Markdown every time.

## Files

- `match_observations.csv`: one locked observation per row.

## Row rules

- Use one row per locked selection, not one row per match.
- Keep official recommendations and simulation-only observations separated.
- Do not backfill a selection that was not locked before kickoff.
- Leave settlement fields blank until a reviewed result is available.
- Use `profit = return_amount - 1.00` for settled 1u single-selection simulation.
- If the report only defined a threshold, record the threshold in `odds_at_lock` and explain it in `notes`.

## Minimum fields to maintain

- lock context: `match_date`, `lock_time`, `source_record`, `snapshot_file`
- market context: `market_type`, `market_scope`, `line`, `selection`, `odds_at_lock`
- model context: `confidence_color`, scores, probability gap when available
- settlement: `result_score`, `settlement`, `hit`, `return_amount`, `profit`, `review_record`

