# Stock Analysis Workflow

Use this for individual A-share stock analysis or a watchlist.

## Steps

1. Normalize ticker and exchange.
2. Validate price, volume, financial, sector, and event data.
3. Identify the stock's current role: market leader, sector leader, follower, defensive holding, turnaround, or high-risk speculation.
4. When value/quality/fund-flow/policy/risk language appears, load `references/five-factor-stock-selection.md` and run the five-step review.
5. Analyze technical structure: trend, volume, support/resistance, gap, limit-up behavior, and relative strength.
6. Analyze fundamentals: revenue, profit, cash flow, margins, valuation, and report period quality.
7. Analyze catalysts: policy, earnings, product, industry, shareholder, M&A, litigation, or rumor.
8. Analyze capital behavior if reliable data exists.
9. Compare against sector peers.
10. Produce a thesis, contradiction list, and conditional action.

## Evidence Layers

| Layer | Questions |
|---|---|
| Value and quality | Is valuation reasonable relative to quality, growth, and peer position? |
| Fundamental base | Do profit trend, cash flow, margins, and leverage support the thesis? |
| Price-volume | Is the move confirmed by volume and relative strength? |
| Capital behavior | Do 1-month funds, turnover, volume ratio, and order imbalance confirm or contradict the move? |
| Sector | Is the stock leading or merely following? |
| Growth/policy | Does industry space or policy support translate into earnings or cash-flow evidence? |
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

