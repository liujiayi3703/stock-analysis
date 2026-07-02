# Connecting Agents

Use this repository as a skill library for AI stock-picking agents, A-share analysis agents, and Serenity-style equity research agents.

## Fast Path

1. Read `manifest.json`.
2. Choose the matching skill entrypoint.
3. Read that skill's `SKILL.md` completely.
4. Load only the workflow and reference files required by the user's current request.

## Skill Router

| User intent | Entrypoint |
|---|---|
| AI选股, find sectors first, map industry chains, screen companies, build a stock shortlist, run three-lens decisions, source-backed ticker research, or macro-event digestion | `skills/ai-stock-picking/SKILL.md` |
| A-share market data, hotspots, market regime, individual stocks, holdings, trade-signal CSV files, or trading suggestions | `skills/a-share-stock-analysis/SKILL.md` |
| Market news to alpha hypothesis, demand-chain impact, small-cap beneficiaries, validation path | `skills/serenity-alpha/SKILL.md` |
| Bayesian intrinsic growth, market-implied growth, FOMO versus fundamentals | `skills/bayesian-intrinsic-growth-valuation/SKILL.md` |
| GF-DMA trend/valuation health, DMA divergence, escape risk, estimate revisions | `skills/gf-dma-health-index/SKILL.md` |
| TAM-adjusted PEG, growth runway, quality-adjusted growth valuation | `skills/tam-adj-peg/SKILL.md` |
| Full buy-side equity research memo, target-price scenarios, catalysts, risks, monitoring dashboard | `skills/buy-side-equity-research-memo/SKILL.md` |

## Five-Factor Routing Notes

When a prompt mentions value factors, quality factors, promising domestic stocks, financial health, profit trend, cash-flow direction, 1-month main-fund flow, volume ratio, turnover, order imbalance / 委比, industry growth, policy support, or risk avoidance:

- use `skills/ai-stock-picking/SKILL.md` for building or ranking a candidate stock pool
- use `skills/a-share-stock-analysis/SKILL.md` for a known stock, watchlist, holding, or operation suggestion
- load the selected skill's `references/five-factor-stock-selection.md`

## Strategy Loop Routing Notes

Use `skills/stock-strategy-loop/SKILL.md` when a prompt asks to:

- use latest portfolio screenshots as the holding source
- run "market analysis -> strategy generation -> simulation/backtest -> self-iteration/optimization"
- create `.stock-loop/positions/positions.json`, `daily_signal.json`, `backtest_result.json`, or `strategy_params.json`
- run a 3-year strict backtest with next-open execution
- optimize only bounded parameters and rule weights without auto-ordering

## App Integration

If the app supports a skills folder, point it at:

```text
skills/
```

If the app expects one skill folder, point it at a specific folder under `skills/`, such as:

```text
skills/a-share-stock-analysis/
skills/ai-stock-picking/
skills/stock-strategy-loop/
skills/serenity-alpha/
```

If the app cannot scan folders, paste or upload:

```text
manifest.json
skills/<selected-skill>/SKILL.md
```

Then let the agent read referenced workflow or reference files on demand.

## Expected Agent Behavior

Agents should not load the full repository by default. Start from the manifest, select one skill, then read the smallest needed set of files.

Common AI stock-picking stages:

- Sector scan: `workflows/macro-sector-scan/WORKFLOW.md`
- Industry-chain map: `workflows/industry-chain-map/WORKFLOW.md`
- Company screening: `workflows/company-screening/WORKFLOW.md`
- Five-factor stock selection: `references/five-factor-stock-selection.md`
- Fundamental deep dive: `workflows/fundamental-deep-dive/WORKFLOW.md`
- Technical assist: `workflows/technical-assist/WORKFLOW.md`
- Thesis validation: `workflows/thesis-validation/WORKFLOW.md`
- Shortlist ranking: `workflows/shortlist-ranking/WORKFLOW.md`
- Three-lens decision review: `workflows/three-lens-decision/WORKFLOW.md`
- Source-backed stock research: `workflows/source-backed-research/WORKFLOW.md`
- Macro event digest: `workflows/macro-event-digest/WORKFLOW.md`

Common A-share stages:

- Market overview: `workflows/market-analysis/WORKFLOW.md`
- Hotspot discovery: `workflows/market-hotspots/WORKFLOW.md`
- Individual stock analysis: `workflows/stock-analysis/WORKFLOW.md`
- Five-factor stock/holding review: `references/five-factor-stock-selection.md`
- Holdings review: `workflows/portfolio-review/WORKFLOW.md`
- Data validation: `workflows/data-validation/WORKFLOW.md`
- Trade-signal quality gate: `workflows/signal-quality-gate/WORKFLOW.md`
- Trading suggestion: `workflows/recommendation/WORKFLOW.md`

Common stock strategy loop stages:

- Screenshot scan: `scripts/run_loop.py scan-screenshots`
- Positions extraction contract: `references/positions-schema.md`
- Loop output contracts: `references/loop-contracts.md`
- Loop runner: `scripts/run_loop.py run`

Serenity skills are standalone skills. Their supporting framework material lives in each skill's `references/original-framework.md`.

## Minimum User Inputs

For market work:

- analysis date
- target market scope
- data sources or files
- desired horizon

For stock work:

- ticker and exchange if known
- analysis date
- horizon
- available price, volume, fundamentals, news, and sector data
- for five-factor review: value/quality metrics, latest financials, 1-month fund-flow/trading-health fields, industry/policy evidence, and known risk events when available

For holdings review:

- holdings table or text
- cost basis if available
- share count or weight
- target horizon
- risk tolerance or max drawdown preference

For stock strategy loops:

- workspace containing screenshots or an existing `.stock-loop/positions/positions.json`
- `a-share-data` skill path if not installed in the default local location
- whether to include event fetches
- desired backtest end date if not today
