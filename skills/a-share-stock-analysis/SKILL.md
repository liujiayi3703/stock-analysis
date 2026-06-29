---
name: a-share-stock-analysis
description: Use when the user asks for A-share, China stock market, 沪深A股, market hotspot, sector theme, individual stock, portfolio holding, 持仓, 行情数据, trading suggestion, risk review, data validation, or evidence-based stock decision support.
---

# A-Share Stock Analysis

Route A-share market questions through a staged workflow: identify the task, validate data, analyze evidence, then produce decision support with explicit risk controls.

## First Rule

Do not load the whole suite by default. Read only the workflow and reference files needed for the current stage. If live market, news, policy, exchange rule, index constituent, or corporate event data is needed, verify it with current sources before relying on it.

## Safety Boundary

This skill produces decision support, not guaranteed investment advice. Always separate:

- evidence: observed data and cited sources
- inference: what the evidence may imply
- uncertainty: missing data, conflicting signals, timing risk
- suggestion: watch, hold, add, reduce, avoid, or conditional action
- invalidation: what would prove the thesis wrong

Never present a buy or sell suggestion without risk controls.

## Router

| User intent | Read first | Also read when needed |
|---|---|---|
| Find, collect, or inspect A-share data sources | `workflows/data-discovery/WORKFLOW.md` | `references/data-sources.md` |
| Check whether market or holdings data is trustworthy | `workflows/data-validation/WORKFLOW.md` | `references/validation-checklist.md`, `references/output-schemas.md` |
| Discover market hotspots, sector themes, main lines, 涨停/成交额/资金主线 | `workflows/market-hotspots/WORKFLOW.md` | `references/a-share-domain.md`, `references/data-sources.md` |
| Analyze broad market conditions, indices, sentiment, liquidity, risk appetite | `workflows/market-analysis/WORKFLOW.md` | `references/a-share-domain.md`, `references/risk-policy.md` |
| Analyze one stock or a watchlist | `workflows/stock-analysis/WORKFLOW.md` | `references/output-schemas.md`, `references/risk-policy.md` |
| Review user-provided holdings or portfolio | `workflows/portfolio-review/WORKFLOW.md` | `references/output-schemas.md`, `references/risk-policy.md` |
| Validate trade signals or simulated broker instruction files | `workflows/signal-quality-gate/WORKFLOW.md` | `references/trading-signal-schema.md`, `references/output-schemas.md` |
| Produce final operation suggestions | `workflows/recommendation/WORKFLOW.md` | `references/risk-policy.md`, relevant report template |

If the request spans multiple stages, run them in this order:

1. Data discovery
2. Data validation
3. Market hotspot or market analysis
4. Stock, portfolio, or signal analysis
5. Recommendation

## Input Contract

Ask for missing inputs only when the answer would otherwise be unsafe or empty. Use reasonable defaults for non-critical details and state them.

Minimum useful inputs:

- analysis date and market session
- market scope or stock tickers
- available files, sources, or APIs
- horizon: intraday, swing, medium-term, long-term
- for holdings: ticker, name, shares or weight, cost basis if available

## Output Defaults

Use the user's language. For Chinese users, default to Simplified Chinese. Prefer concise tables plus short interpretation.

Every final analysis should include:

- data coverage and freshness
- core conclusion
- evidence table
- risks and contradictory signals
- next checks
- conditional suggestion with invalidation line

## Bundled Tools

- `scripts/validate_holdings_csv.py`: validate holdings CSV columns and basic numeric fields.
- `scripts/validate_market_dataset.py`: validate common market dataset fields, dates, duplicates, and missing values.
- `scripts/validate_trade_signals.py`: validate A-share trade-signal CSV files, duplicate signal IDs, lot sizes, directions, prices, and timestamps.
