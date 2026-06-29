# Shortlist Ranking Workflow

Use this at the end of the pipeline to rank candidates.

## Steps

1. Combine sector score, profit-pool score, company quality, valuation, technical state, and risk flags.
2. Rank candidates by evidence quality, not only upside imagination.
3. Assign action framing:
   - exclude
   - watchlist
   - deep-dive
   - conditional trial
   - existing-position review
4. Attach invalidation conditions and next data checks.
5. Use `a-share-stock-analysis/workflows/recommendation/WORKFLOW.md` for final risk-aware suggestions.

## Ranking Matrix

| Ticker | Sector score | Chain score | Fundamental score | Valuation score | Technical score | Risk flags | Final rank |
|---|---:|---:|---:|---:|---:|---|---:|

## Output

Use `templates/stock-picking-final-report.md`.

Never present the ranking as a guaranteed return forecast.

