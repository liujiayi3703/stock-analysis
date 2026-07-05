---
name: stock-strategy-loop
description: "A-share holding strategy loop: turn portfolio screenshots or positions JSON into market/news collection, holding actions, strict backtests, bounded optimization, and Markdown plus JSON outputs without auto-ordering."
---

# Stock Strategy Loop

## Purpose

Use this skill to run a repeatable research loop for the user's A-share holdings:

`latest screenshot holdings -> market analysis -> strategy signal -> strict backtest -> bounded parameter/weight optimization -> Markdown + JSON report`

This is a research and simulation workflow. It does not place orders, bypass risk controls, or output unconditional buy/sell instructions.

## Required Inputs

- A workspace folder containing portfolio screenshots. Screenshot filenames are treated as the screenshot time.
- A structured positions file at `.stock-loop/positions/positions.json`.
- The positions file is normally produced by Codex vision from the latest screenshots. Local OCR is not assumed.

Read `references/positions-schema.md` before creating or editing `positions.json`. Read `references/loop-contracts.md` before interpreting or changing `daily_signal.json`, `strategy_params.json`, `backtest_result.json`, or optimization results.

## Existing Skills To Reuse

- Use `a-share-data` scripts for A-share market data, history, indicators, fund flow, sectors, events, and board heat.
- Use market-news collection for weekend/current-market context before interpreting next-week holding actions.
- Treat `data_coverage` and `data_confidence` as first-class risk controls; downgrade actions when quotes, history, fund flow, or events are missing.
- Use `macd-trend-resonance-stock-picker`, `macd-second-golden-cross`, and `tuige-shortline-trading` as rule lenses when explaining the strategy result.
- Do not edit those skills as part of this loop. This skill is the orchestrator.

## Standard Workflow

### 1. Scan latest screenshots

Run:

```powershell
$SKILL_DIR = "<path-to-this-skill>"
python "$SKILL_DIR\scripts\run_loop.py" `
  --workspace "<workspace>" scan-screenshots
```

This writes `.stock-loop/positions/latest_screenshots.json`.

### 2. Extract positions with Codex vision

Open the latest screenshot images listed in `latest_screenshots.json`. Extract every visible account and holding into `.stock-loop/positions/positions.json`.

Required holding fields:

- `code`
- `name`
- `shares`
- `cost_price`
- `last_price`
- `market_value`
- `unrealized_pnl`

If any required field cannot be read, stop and report the missing field. Do not invent data.

### 3. Validate positions

Run:

```powershell
python "$SKILL_DIR\scripts\run_loop.py" `
  validate-positions --positions-json "<workspace>\.stock-loop\positions\positions.json"
```

Proceed only if validation succeeds. The validator checks required fields and basic arithmetic consistency.

### 4. Run the loop

Run:

```powershell
python "$SKILL_DIR\scripts\run_loop.py" `
  --workspace "<workspace>" `
  run --include-events `
  --a-share-skill "<path-to-a-share-data-skill>"
```

If `--a-share-skill` is omitted, the runner checks `A_SHARE_SKILL_DIR`, then falls back to `C:\Users\liuji\.codex\skills\a-share-data`.

Outputs are written to:

- `.stock-loop/runs/YYYY-MM-DD/report.md`
- `.stock-loop/runs/YYYY-MM-DD/daily_signal.json`
- `.stock-loop/backtests/backtest_result_YYYY-MM-DD.json`
- `.stock-loop/backtests/optimization_YYYY-MM-DD.json`
- `.stock-loop/params/strategy_params.json`

The runner now records:

- per-run data coverage for quotes, history, fund flow, events, board summaries, indices, and market news
- 5-day main-fund-flow net value in each stock score's raw evidence
- broad market-news topic hits so weekend news can be considered alongside technical and fund-flow signals
- degraded event-fetch fallback when sentiment/event enrichment is slow or unavailable

## Strategy Contract

Allowed actions are fixed:

- `hold`
- `reduce`
- `exit`
- `watch`
- `add_only_if_triggered`

Every action must include:

- reason
- trigger
- invalidation
- target weight
- risk note

## Backtest Contract

The runner uses:

- latest screenshot holdings as the stock universe
- recent 3-year daily history by default
- signal after close, execution at next open
- no future data
- max 8 holdings
- max 15% single-stock target weight
- default roundtrip friction 45 bps
- missing/open-invalid/untradable rows skipped rather than guessed

The backtest must report:

- annualized return
- max drawdown
- Sharpe
- win rate
- profit/loss ratio
- trade count
- turnover
- max single trade loss
- max consecutive losses

## Optimization Contract

Optimization may adjust only:

- moving-average periods
- MACD parameters
- signal weights
- fund-flow threshold behavior
- stop-loss threshold
- take-profit/trailing-profit threshold
- max holdings and max single-stock weight

The runner currently evaluates bounded candidate parameter sets with walk-forward validation. A candidate is promoted only if sample-out risk-adjusted score improves and drawdown/trade-count/loss guardrails remain acceptable.

Do not let the model rewrite trading rules automatically. If a rule change is desired, propose it to the user as a separate explicit change.

## Report Style

Keep the final user response concise. Include:

- where the report was written
- whether positions validation passed
- key portfolio actions
- backtest/optimization status
- data failures that lower confidence

Do not paste full JSON unless asked.

## Failure Handling

- If no positions JSON exists, run screenshot scan and ask the user/vision step to extract positions.
- If positions validation fails, stop. Do not run market analysis from bad holdings.
- If a market data endpoint fails, continue where possible and mark the item as low confidence.
- If too few history rows exist, skip optimization and state why.
