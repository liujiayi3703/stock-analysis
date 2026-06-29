# Portfolio Review Workflow

Use this when the user provides holdings, positions, cost basis, watchlists, or asks what to do with current stocks.

## Steps

1. Parse holdings into the schema in `references/output-schemas.md`.
2. Validate holdings with `scripts/validate_holdings_csv.py` when CSV is available.
3. Ask for cost basis or holding thesis only if absent data changes the conclusion materially.
4. Classify each holding by role: core, satellite, trade, hedge, watch, or error position.
5. Measure concentration by sector, theme, market cap, and correlated catalysts.
6. Review each stock using `stock-analysis` at the depth required by position size.
7. Map actions: keep, add conditionally, reduce, replace, hedge, or watch.
8. Provide portfolio-level risk controls.

## Priority Rules

- Larger weights deserve deeper evidence.
- Losing positions need invalidation and recovery conditions, not emotional averaging-down.
- Winning positions need trailing risk controls and catalyst freshness checks.
- Theme concentration can be risky even when each stock looks acceptable alone.

## Output

Use `templates/portfolio-review.md`.

Include:

- portfolio diagnosis
- position table
- action priority
- what data is missing
- next review trigger

