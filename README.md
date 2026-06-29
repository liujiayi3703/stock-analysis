# stock-analysis

Reusable agent skills for A-share market research, hotspot discovery, data validation, portfolio review, and evidence-based trading decision support.

## Entry Point

Agents should start with:

`skills/a-share-stock-analysis/SKILL.md`

The root skill is a router. It keeps the first read small, then points the agent to the workflow and reference files needed for the current task.

## Install Or Connect

Use the repository as a skill source in any agent app that supports a skills directory:

```text
skills/a-share-stock-analysis/
```

For apps that cannot scan a skills directory, read `manifest.json` first, then load the listed `entrypoint`.

## Scope

This skill suite helps agents:

- collect and inspect A-share market data
- discover market hotspots and sector themes
- validate data quality before analysis
- produce market-level and stock-level analysis
- review user-provided holdings
- output decision-support suggestions with risk controls

It does not guarantee investment returns. Every suggestion must separate evidence, inference, uncertainty, and risk controls.

