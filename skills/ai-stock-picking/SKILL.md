---
name: ai-stock-picking
description: Use when the user asks for AI stock picking, 选股, 找赛道, 风口行业, 产业链拆解, 股票池筛选, 三高公司, high-growth high-margin moat companies, stock shortlist, or a sector-first company-picking workflow that combines macro, policy, earnings, fundamentals, technicals, and risk validation.
---

# AI Stock Picking

Use AI as an intelligence analyst and validation assistant, not as an oracle. Run a sector-first pipeline: find where money and fundamentals may flow, map the value chain, screen companies, validate the thesis, then produce a risk-aware shortlist.

## First Rule

Do not jump directly to tickers. Start with sector and industry-chain reasoning unless the user explicitly provides a stock or portfolio. For current market, policy, earnings, price, or news facts, verify with fresh sources before relying on them.

## Safety Boundary

This skill produces research support, not guaranteed investment advice. Always separate:

- facts: verified data and sources
- thesis: why a sector or company may matter
- validation: what data supports or rejects it
- uncertainty: missing data and contradiction
- action framing: observe, exclude, deep-dive, watchlist, or conditional trial

Never output a simple "buy list" without validation status, risk flags, and invalidation conditions.

## Pipeline Router

Run the stages in order unless the user asks for a specific stage:

| Stage | Read first | Purpose |
|---|---|---|
| 1. Sector scan | `workflows/macro-sector-scan/WORKFLOW.md` | Find 6-12 month sectors from economic cycle, policy direction, and earnings growth |
| 2. Industry-chain map | `workflows/industry-chain-map/WORKFLOW.md` | Map upstream/midstream/downstream and identify profit pools |
| 3. Company screening | `workflows/company-screening/WORKFLOW.md` | Build a stock pool with quantitative and qualitative filters |
| 4. Fundamental deep dive | `workflows/fundamental-deep-dive/WORKFLOW.md` | Validate ROE, cash flow, leverage, margins, and growth quality |
| 5. Technical assist | `workflows/technical-assist/WORKFLOW.md` | Use price-volume, trend, support/resistance, MACD/RSI as secondary evidence |
| 6. Thesis validation | `workflows/thesis-validation/WORKFLOW.md` | Reject fake narratives, concept chasing, and weak evidence |
| 7. Shortlist ranking | `workflows/shortlist-ranking/WORKFLOW.md` | Rank candidates and produce a conditional action shortlist |

## Optional Specialist Workflows

Load these only when the user's request matches the need:

| Need | Read first | Also read |
|---|---|---|
| Three-lens decision review combining macro, supply-chain chokepoints, and execution timing | `workflows/three-lens-decision/WORKFLOW.md` | `references/three-lens-framework.md` |
| Source-backed individual stock research, target price scenarios, stop-loss, and entry plan | `workflows/source-backed-research/WORKFLOW.md` | `references/source-backed-research-checklist.md` |
| Macro event or central-bank speech digest for market impact and expectation gaps | `workflows/macro-event-digest/WORKFLOW.md` | `references/macro-event-framework.md` |

## Sub-Skill Routing

Use these existing skills as specialist modules:

| Need | Use |
|---|---|
| A-share market, hotspot, stock, holding, or recommendation workflow | `a-share-stock-analysis` |
| News-to-alpha, demand-chain impact, small-cap beneficiary discovery | `serenity-alpha` |
| Intrinsic 3-5 year growth versus market-implied growth | `bayesian-intrinsic-growth-valuation` |
| Trend and valuation health, DMA divergence, escape risk | `gf-dma-health-index` |
| Growth-stock valuation with TAM runway and quality adjustment | `tam-adj-peg` |
| Full source-backed company memo | `buy-side-equity-research-memo` |

## Required Output Shape

For full-pipeline requests, use `templates/stock-picking-final-report.md`.

Minimum final sections:

- sector candidates and why
- industry-chain profit-pool map
- screened company pool
- fundamental validation
- technical assist signals
- red flags and exclusions
- final shortlist with confidence, invalidation, and next checks

## Stop Conditions

Stop or downgrade confidence when:

- current data is unavailable or stale
- the sector thesis depends only on slogans or unverified rumors
- a company has no earnings, orders, cash-flow, or margin evidence
- the stock is ST, under delisting risk, or has material unresolved governance risk
- technical strength contradicts fundamentals and cannot be explained

## Source Discipline

This suite may learn from public repositories and articles, but agents must not copy third-party text or code unless licensing allows it and attribution is preserved. See `../../docs/THIRD_PARTY_SOURCES.md` for source notes.
