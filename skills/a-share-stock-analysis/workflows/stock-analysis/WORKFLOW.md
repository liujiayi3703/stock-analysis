# Stock Analysis Workflow

Use this for individual A-share stock analysis or a watchlist.

## Steps

1. Normalize ticker and exchange.
2. Validate price, volume, financial, sector, and event data.
3. Identify the stock's current role: market leader, sector leader, follower, defensive holding, turnaround, or high-risk speculation.
4. Analyze technical structure: trend, volume, support/resistance, gap, limit-up behavior, and relative strength.
5. Analyze fundamentals: revenue, profit, cash flow, margins, valuation, and report period quality.
6. Analyze catalysts: policy, earnings, product, industry, shareholder, M&A, litigation, or rumor.
7. Analyze capital behavior if reliable data exists.
8. Compare against sector peers.
9. Produce a thesis, contradiction list, and conditional action.

## Evidence Layers

| Layer | Questions |
|---|---|
| Price-volume | Is the move confirmed by volume and relative strength? |
| Sector | Is the stock leading or merely following? |
| Fundamentals | Does business performance support the market narrative? |
| Catalyst | Is the catalyst verified and still active? |
| Risk | What would make the thesis wrong quickly? |

## Output

Use `templates/stock-report.md`.

Never output a simple "buy" or "sell" label. Use conditional suggestions:

- watch
- hold
- add only if condition X confirms
- reduce if condition Y breaks
- avoid because evidence is insufficient

