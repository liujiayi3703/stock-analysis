---
name: stock-strategy-loop
description: "A-share holding strategy loop: turn portfolio screenshots or positions JSON into market/news collection, holding actions, industry panorama cognition 行业全景认知, strict backtests, bounded optimization, and Markdown plus JSON outputs without auto-ordering."
---

# Stock Strategy Loop

## Purpose

Use this skill to run a repeatable research loop for the user's A-share holdings:

`latest screenshot holdings -> market analysis -> strategy signal -> strict backtest -> bounded parameter/weight optimization -> Markdown + JSON report`

This is a research and simulation workflow. It does not place orders, bypass risk controls, or output unconditional buy/sell instructions.

## Required Inputs

- A workspace folder containing screenshots for one account. The scanner reads only direct child screenshots with a parseable timestamp; use one sibling folder per account and pass that folder as `--workspace` so runtime state cannot cross accounts.
- A structured positions file at `.stock-loop/positions/positions.json`.
- The positions file is normally produced by Codex vision from the latest screenshots. Local OCR is not assumed.

Read `references/positions-schema.md` before creating or editing `positions.json`. Read `references/loop-contracts.md` before interpreting or changing `daily_signal.json`, `strategy_params.json`, `backtest_result.json`, or optimization results.

## Existing Skills To Reuse

- Use `a-share-data` scripts for A-share market data, history, indicators, fund flow, sectors, events, and board heat.
- Use market-news collection for weekend/current-market context before interpreting next-week holding actions.
- Treat `data_coverage` and `data_confidence` as first-class risk controls; downgrade actions when quotes, history, fund flow, or events are missing.
- Use `macd-trend-resonance-stock-picker`, `macd-second-golden-cross`, and `tuige-shortline-trading` as rule lenses when explaining the strategy result.
- Use `industry-panorama-cognition` for material holdings so the report includes 行业全景认知: each stock's segment, upstream/midstream/downstream position, industry influence, scarce capability checks, and a clear analogy when useful.
- Do not edit those skills as part of this loop. This skill is the orchestrator.

## Standard Workflow

The system has two manual entry points:

- `run`: account-screenshot loop. It runs only after a new validated screenshot is added and the user explicitly invokes the command, records the signal and data coverage, then uses the next new screenshot to review observed share changes.
- `analyze-targets`: standalone research that runs only when explicitly invoked for user-supplied six-digit A-share codes. It can use current account context when available, but it does not update the account loop state/history or create an order.

### 1. Scan latest screenshots

Run:

```powershell
$SKILL_DIR = "<path-to-this-skill>"
python "$SKILL_DIR\scripts\run_loop.py" `
  --workspace "<workspace>" scan-screenshots
```

If a legacy `positions.json` contains multiple accounts, pass `--account <account-name>` to `validate-positions` and `run`; otherwise the runner stops rather than combining cash, weights, and risk limits across accounts.
When there is one named `accounts[]` row and all holdings omit the optional `account`, validation assigns the holdings to that account. Mixed named/unnamed holdings and unnamed holdings with multiple account rows are rejected as ambiguous.

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
If cash or total assets are unreadable, preserve exact boolean coverage markers from the schema; reports then show account exposure as unknown and normalize concentration only within visible holdings.

### 3. Validate positions

Run:

```powershell
python "$SKILL_DIR\scripts\run_loop.py" `
  validate-positions --positions-json "<workspace>\.stock-loop\positions\positions.json"
```

Proceed only if validation succeeds. Its positions-only numeric parser accepts only finite built-in integers/floats and rejects booleans, numeric strings, and containers without changing permissive vendor-data parsing elsewhere. Market-value derivation is allowed only for an omitted field with exact `market_value_derived: true`; strict top-level asset semantics and arithmetic consistency are also enforced.

### 4. Run the loop

Run:

```powershell
python "$SKILL_DIR\scripts\run_loop.py" `
  --workspace "<workspace>" `
  run --include-events `
  --a-share-skill "<path-to-a-share-data-skill>"
```

If `--a-share-skill` is omitted, the runner checks `A_SHARE_SKILL_DIR`, then falls back to the current user's `.codex/skills/a-share-data` directory. Network fallbacks require `requests>=2.31,<3`; offline screenshot scanning and positions validation do not.

Outputs are written to:

- `.stock-loop/runs/YYYY-MM-DD-HH-MM-SS/report.md`
- `.stock-loop/runs/YYYY-MM-DD-HH-MM-SS/daily_signal.json`
- `.stock-loop/backtests/backtest_result_YYYY-MM-DD.json`
- `.stock-loop/backtests/optimization_YYYY-MM-DD.json`
- `.stock-loop/params/strategy_params.json`

An account run leaves the existing input manifest and normalized positions untouched while it builds and validates the analysis. After the report and staged artifacts are complete, both account inputs are committed through the same recovery journal as strategy parameters, market history, and loop state. Any failure preserves their exact prior bytes or continued absence. A run or target analysis directory is first completed in a hidden staging directory and then published with one rename; failures return a structured status and remove partial output.

The runner now records:

- per-run data coverage for quotes, history, fund flow, events, board summaries, indices, and market news
- 5-day main-fund-flow net value in each stock score's raw evidence, or `null` when no valid fund-flow row exists; missing fund flow stays null publicly while `score_imputations.fund_flow: 50.0` records the neutral value used only inside the total score
- broad market-news topic hits so weekend news can be considered alongside technical and fund-flow signals
- degraded event-fetch fallback when sentiment/event enrichment is slow or unavailable

Independent board modes and per-stock history/fund-flow/event requests run concurrently (up to eight stock workers). Each source failure remains attached to the affected code or coverage field rather than blocking the rest of the account.

After a completed new-screenshot run, the runner writes `.stock-loop/state/loop_state.json` plus `loop_review.json` in the run folder. Repeating the same screenshot returns `unchanged_snapshot` before collection. A later screenshot records observed share changes against the prior action using neutral wording; it never asserts that an action was executed.

Every completed report contains: core conclusion; data coverage/freshness; today's market; recent/today main lines and evidence-backed leader roles; fact-logic-scenario chains; 1-5 day and 1-3 month outlooks; portfolio diagnosis; per-holding analysis/action; backtest/optimization limits; and loop review/next checks.

Missing board detail suppresses leader claims. Missing breadth/turnover downgrades the market regime. Fewer than three distinct recent market sessions prevents `confirmed_mainline`. These degradations remain visible in Markdown and JSON.

### 5. Research specified stocks

Run this when the user asks for one or more target stocks rather than a full account review:

```powershell
python "$SKILL_DIR\scripts\run_loop.py" `
  --workspace "<account workspace or research workspace>" `
  analyze-targets --codes "000101,000202" --include-events
```

Use only six-digit A-share codes. If a target is already held in the account positions file, the report retains its cost, shares, and account weight. A non-held target is research-only: the output is `watch` with `0%` target weight. Results are isolated under `.stock-loop/analyses/`.
For incomplete-asset accounts, target subsets retain the full visible account stock-value denominator, so a one-stock target is not relabeled as 100% of the visible account.

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

When a held stock has no usable daily bar, its valuation carries forward the last valid close while trading remains blocked. The output is marked `technical_only_diagnostic` when the backtest lacks point-in-time fund-flow, sector, and event inputs; such a run cannot automatically promote new live parameters.

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
- industry panorama cognition for material holdings
- backtest/optimization status
- data failures that lower confidence

Do not paste full JSON unless asked.

## Failure Handling

- If no positions JSON exists, run screenshot scan and ask the user/vision step to extract positions.
- If positions validation fails, stop. Do not run market analysis from bad holdings.
- If a market data endpoint fails, continue where possible and mark the item as low confidence.
- If too few history rows exist, skip optimization and state why.
- If output publication returns `artifact_write_failed`, do not use the incomplete result; the runner restores prior account inputs/backtest files and removes staged directories where cleanup succeeds.
