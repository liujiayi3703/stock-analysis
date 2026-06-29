# stock-analysis

Reusable agent skills for AI-assisted stock picking, A-share market research, hotspot discovery, data validation, trade-signal audit, portfolio review, Serenity equity research frameworks, and evidence-based trading decision support.

## Entry Points

Agents should start with `manifest.json`, then load the skill that matches the task.

Default stock-picking router:

```text
skills/ai-stock-picking/SKILL.md
```

A-share analysis router:

```text
skills/a-share-stock-analysis/SKILL.md
```

Serenity framework skills:

```text
skills/serenity-alpha/SKILL.md
skills/bayesian-intrinsic-growth-valuation/SKILL.md
skills/gf-dma-health-index/SKILL.md
skills/tam-adj-peg/SKILL.md
skills/buy-side-equity-research-memo/SKILL.md
```

## Install Or Connect

Use the repository as a skill source in any agent app that supports a skills directory:

```text
skills/
```

If an app expects one skill folder, point it at the specific folder under `skills/`.

For apps that cannot scan a skills directory, read `manifest.json` first, then load the listed `entrypoint`.

## Scope

This skill library helps agents:

- run a sector-first stock-picking pipeline
- collect and inspect A-share market data
- discover market hotspots and sector themes
- validate data quality before analysis
- produce market-level and stock-level analysis
- review user-provided holdings
- map industry chains and identify profit pools
- run three-lens decision reviews across macro, industry-chain, and execution timing
- screen high-growth, high-margin, high-bargaining-power companies
- produce source-backed stock research reports with target-price scenarios and stop-loss logic
- digest macro events from primary sources and expectation gaps
- validate A-share trade-signal CSV files before simulation or upload
- translate market news into alpha hypotheses
- evaluate growth stocks with Bayesian intrinsic growth, GF-DMA, and TAM-Adj-PEG frameworks
- generate buy-side equity research memos
- output decision-support suggestions with risk controls

It does not guarantee investment returns. Every suggestion must separate evidence, inference, uncertainty, and risk controls.

## Source Notes

Some workflow ideas were learned from public stock-related repositories and rewritten for this library. See `docs/THIRD_PARTY_SOURCES.md` for licensing and attribution notes.
