# Connecting Agents

Use this repository as a skill library for A-share analysis agents.

## Fast Path

1. Read `manifest.json`.
2. Load `skills/a-share-stock-analysis/SKILL.md`.
3. Follow the router table in `SKILL.md`.
4. Load only the workflow and reference files required by the user's current request.

## App Integration

If the app supports a skills folder, point it at:

```text
skills/
```

If the app expects one skill folder, point it at:

```text
skills/a-share-stock-analysis/
```

If the app cannot scan folders, paste or upload:

```text
manifest.json
skills/a-share-stock-analysis/SKILL.md
```

Then let the agent read referenced workflow files on demand.

## Expected Agent Behavior

Agents should not load the full repository by default. Start from the root skill, identify the current stage, then read the smallest needed set of files.

Common stages:

- Market overview: `workflows/market-analysis/WORKFLOW.md`
- Hotspot discovery: `workflows/market-hotspots/WORKFLOW.md`
- Individual stock analysis: `workflows/stock-analysis/WORKFLOW.md`
- Holdings review: `workflows/portfolio-review/WORKFLOW.md`
- Data validation: `workflows/data-validation/WORKFLOW.md`
- Trading suggestion: `workflows/recommendation/WORKFLOW.md`

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

