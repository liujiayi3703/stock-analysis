# Data Discovery Workflow

Use this when the task needs A-share market, sector, stock, holdings, financial, news, or fund-flow data.

## Steps

1. Define the analysis scope: date, market, indices, sectors, stocks, and horizon.
2. Inventory available local files first.
3. Identify missing fields required by the target workflow.
4. Prefer authoritative or reproducible sources over screenshots and unsourced summaries.
5. Record source name, retrieval time, field definitions, and known delays.
6. Hand off to `data-validation` before analysis.

## Minimum Dataset Map

| Need | Fields |
|---|---|
| Market breadth | trade date, advancers, decliners, limit-up count, limit-down count, turnover |
| Sector hotspot | sector name, constituent returns, sector turnover, leader stocks, catalyst |
| Stock price-volume | ticker, date/time, open, high, low, close, volume, amount, adjustment flag |
| Fundamentals | ticker, report period, revenue, profit, cash flow, margins, valuation |
| Holdings | ticker, name, shares or weight, cost basis, latest price, holding thesis |

## Source Notes

Read `references/data-sources.md` for source selection. For current market facts, browse or query live sources and cite them. Do not treat cached data as current unless timestamped.

## Handoff

Return:

- scope and assumptions
- data files or URLs found
- missing fields
- source timestamps
- recommended validation checks

