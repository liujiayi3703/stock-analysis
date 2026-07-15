# Portfolio Review Workflow

Use this when the user provides holdings, positions, cost basis, watchlists, or asks what to do with current stocks.

## Steps

1. Parse holdings into the schema in `references/output-schemas.md`.
2. Validate holdings with `scripts/validate_holdings_csv.py` when CSV is available.
3. Ask for cost basis or holding thesis only if absent data changes the conclusion materially.
4. Classify each holding by role: core, satellite, trade, hedge, watch, or error position.
5. Measure concentration by sector, theme, market cap, and correlated catalysts.
6. For each material holding, use `industry-panorama-cognition` when available, or load `references/industry-panorama-template.md`, and explain its segment, value-chain position, industry influence, scarce capability, and one memorable analogy when useful.
7. Review each stock using `stock-analysis` at the depth required by position size.
8. For material positions or operation-analysis requests, apply `references/five-factor-stock-selection.md` so each action has value/quality, fundamental-base, capital-behavior, growth/policy, and risk evidence.
9. Map actions: keep, add conditionally, reduce, replace, hedge, or watch.
10. Provide portfolio-level risk controls.

## Priority Rules

- Larger weights deserve deeper evidence.
- Losing positions need invalidation and recovery conditions, not emotional averaging-down.
- Winning positions need trailing risk controls and catalyst freshness checks.
- Theme concentration can be risky even when each stock looks acceptable alone.
- A position with weak fundamentals and weak 1-month capital behavior should not be upgraded only because valuation looks cheap.

## Output

Use `templates/portfolio-review.md`.

Include:

- portfolio diagnosis
- position table
- industry panorama cognition for material holdings
- action priority
- what data is missing
- next review trigger

