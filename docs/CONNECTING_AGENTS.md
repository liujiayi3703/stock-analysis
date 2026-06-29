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
| AI选股, find sectors first, map industry chains, screen companies, build a stock shortlist | `skills/ai-stock-picking/SKILL.md` |
| A-share market data, hotspots, market regime, individual stocks, holdings, or trading suggestions | `skills/a-share-stock-analysis/SKILL.md` |
| Market news to alpha hypothesis, demand-chain impact, small-cap beneficiaries, validation path | `skills/serenity-alpha/SKILL.md` |
| Bayesian intrinsic growth, market-implied growth, FOMO versus fundamentals | `skills/bayesian-intrinsic-growth-valuation/SKILL.md` |
| GF-DMA trend/valuation health, DMA divergence, escape risk, estimate revisions | `skills/gf-dma-health-index/SKILL.md` |
| TAM-adjusted PEG, growth runway, quality-adjusted growth valuation | `skills/tam-adj-peg/SKILL.md` |
| Full buy-side equity research memo, target-price scenarios, catalysts, risks, monitoring dashboard | `skills/buy-side-equity-research-memo/SKILL.md` |

## App Integration

If the app supports a skills folder, point it at:

```text
skills/
```

If the app expects one skill folder, point it at a specific folder under `skills/`, such as:

```text
skills/a-share-stock-analysis/
skills/ai-stock-picking/
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
- Fundamental deep dive: `workflows/fundamental-deep-dive/WORKFLOW.md`
- Technical assist: `workflows/technical-assist/WORKFLOW.md`
- Thesis validation: `workflows/thesis-validation/WORKFLOW.md`
- Shortlist ranking: `workflows/shortlist-ranking/WORKFLOW.md`

Common A-share stages:

- Market overview: `workflows/market-analysis/WORKFLOW.md`
- Hotspot discovery: `workflows/market-hotspots/WORKFLOW.md`
- Individual stock analysis: `workflows/stock-analysis/WORKFLOW.md`
- Holdings review: `workflows/portfolio-review/WORKFLOW.md`
- Data validation: `workflows/data-validation/WORKFLOW.md`
- Trading suggestion: `workflows/recommendation/WORKFLOW.md`

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

For holdings review:

- holdings table or text
- cost basis if available
- share count or weight
- target horizon
- risk tolerance or max drawdown preference
