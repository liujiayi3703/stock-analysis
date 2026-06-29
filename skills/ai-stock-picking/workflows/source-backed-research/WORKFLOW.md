# Source-Backed Research Workflow

Use this workflow for a ticker-level research report before entering, adding, reducing, or updating a position.

## Inputs

- ticker and exchange
- current price and analysis date
- available data sources: broker fundamentals, exchange filings, company IR, financial statements, analyst consensus, industry data, or market data files
- target holding horizon and risk tolerance

## Procedure

1. Load `references/source-backed-research-checklist.md`.
2. Collect evidence in three buckets:
   - current fundamentals and valuation anchors
   - multi-year historical financials and valuation range
   - market expectations, ownership, catalysts, and risk signals
3. Reconcile share count and market value using the freshest source. Do not mix stale annual share counts with current price.
4. Calculate three scenarios:
   - bear: conservative growth and multiple
   - base: evidence-supported growth and normal multiple
   - bull: upside growth and premium multiple with explicit catalyst
5. Separate two risk levels:
   - operational stop or risk-control level based on price action and volatility
   - fundamental downside level based on conservative valuation and realized revenue/earnings
6. Check the 12 quality and red-flag items before any action framing.
7. Compare analyst consensus target with current price. If consensus target is near current price, require stronger catalyst evidence for upside.
8. Produce a report with assumptions, formulas, data freshness, contradictions, and next update triggers.

## Output

Use `templates/source-backed-research-report.md` when a full report is requested.

Minimum sections:

- investment question and answer-first view
- source inventory and freshness
- business and industry-chain role
- fundamentals table
- valuation anchors and scenario table
- ownership, insider, and institutional signals
- red flags and contradiction log
- target price range, risk controls, and invalidation
- next data to collect

Never present a target price without the assumptions that produced it.
