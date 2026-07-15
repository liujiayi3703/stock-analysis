# Stock Strategy Loop Contracts

These contracts define the durable JSON interfaces used by `scripts/run_loop.py`.

## Runtime Directories

The runner creates these folders under the selected workspace:

```text
.stock-loop/
  positions/
  runs/YYYY-MM-DD-HH-MM-SS/
  backtests/
  params/
  cache/
  state/
  analyses/
  market-history/
```

Do not treat `.stock-loop/` as source code. It is a local runtime state directory for portfolio snapshots, reports, backtests, and parameter versions.

Run one account per workspace. If a legacy positions file contains multiple `accounts[]` entries, callers must pass `--account`; the runner rejects ambiguous combined-account analysis. If there is exactly one named `accounts[]` row and every holding omits its optional `account`, the runner assigns those holdings to that sole account. Omitted accounts are rejected as ambiguous when mixed with named holdings or multiple account rows. When an `accounts[]` row is selected, that row is authoritative for `cash`, `stock_value`, `total_assets`, `cash_unreadable`, and `total_assets_lower_bound`: present coverage flags are copied exactly, while absent flags clear stale top-level values from another account.

The account loop is manual-only: it runs only after a new screenshot has been added and the user explicitly invokes `run`. `state/loop_state.json` is written only after a completed new-snapshot run. It stores the snapshot time, compact `{code,name,shares}` holdings, previous actions, data coverage, and run directory for the next manual review. An unchanged snapshot exits before market collection, report replacement, state update, or market-history append.

Target-stock research also requires an explicit `analyze-targets` command. It may read current positions for account context, but it never advances account loop state or appends market history. Both entry points first recover any unfinished account persistence transaction recorded in `state/persistence_transaction.json`; a malformed or unsafe journal stops before account inputs are read.

An account run does not overwrite `positions/latest_screenshots.json` or `positions/positions.json` while analysis and report construction are still in progress. After the report and all staged artifacts are complete, those two account inputs are committed through the same recovery journal as strategy parameters, market history, and loop state. A failure before that final commit preserves the exact prior bytes (or continued absence) of both account inputs. A failure during the commit rolls the whole journaled set back. Run and target report directories are written under a hidden staging directory and become visible only after a final directory rename. A JSON, report, backtest, or rename failure removes the staging/output directory and restores any pre-existing external backtest files; no successful state may point at a partial run.

## daily_signal.json

Required top-level fields:

```json
{
  "report_schema_version": 2,
  "data_coverage": {},
  "evidence_index": [],
  "market_snapshot": {},
  "market_mainlines": [],
  "market_outlook": {},
  "portfolio_diagnosis": {},
  "holding_analyses": [],
  "portfolio_actions": []
}
```

The validator requires `report_schema_version` to be the exact JSON integer `2` (not a boolean, string, or float). Each required top-level value above must use its shown object/list container. The runner also emits compatibility/context fields including `generated_at`, `snapshot_time`, `market_regime`, `market_news_context`, `sector_context`, `industry_panorama`, and `stock_scores`.

Each `evidence_index[]` item requires these contract fields (and may add fields such as `url`):

- `evidence_id`
- `category`
- `statement`
- `source`
- `as_of`
- `trading_session`
- `freshness`: `current-session`, `recent`, `stale`, or `unknown`
- `reliability`: `high`, `medium`, or `low`
- `scope`

Evidence IDs must be non-empty and unique. Every main-line, leader, and holding `evidence_ids[]` list must be non-empty and reference IDs in this registry. Current, recent, or stale evidence requires a non-empty `as_of`; unknown-dated evidence cannot independently support a current-session conclusion.

`market_snapshot` requires `as_of`, `regime`, `confidence`, `indices`, `breadth`, and `missing_evidence`. `regime` is exactly one of `insufficient_evidence`, `high_volatility`, `weak`, `risk_on`, `structural`, or `defensive`. Published index/breadth numbers must be finite and non-boolean; counts are non-negative and coverage ratios stay in `[0, 1]`. Missing breadth or turnover remains explicit and downgrades regime confidence.

Each `market_mainlines[]` item requires:

- `name`, `classification`, `score`, and `score_components`
- `leaders` and `logic_chain`
- `continuation_conditions` and `invalidation_conditions`
- `risk`, `confidence`, and `evidence_ids`
- `catalyst_verified` and `contradictions`

Allowed main-line classifications are:

- `confirmed_mainline`
- `emerging_mainline`
- `today_hotspot`
- `recent_mainline`
- `one_day_noise`
- `insufficient_evidence`

`confirmed_mainline` additionally requires score `>= 70`, known continuity with at least three hits, and no critical contradiction. Continuity is not considered known until at least three distinct recent trading sessions are available.

Main-line `score` is a finite non-boolean JSON number in `[0, 100]`, `catalyst_verified` and any published continuity/contradiction flags are exact booleans, and every score component is finite and non-negative. Approved component maxima are 20 for `same_day_strength`/`continuity` and 15 for `liquidity`/`breadth`/`catalyst_logic`/`leader_structure`; extension components may not exceed 100. Numeric strings, booleans, `NaN`, and infinities are invalid.

Each `leaders[]` item requires `code`, `name`, `role`, `role_evidence`, `confidence`, `risk`, and `evidence_ids`. Allowed leader roles are:

- `emotion_leader`
- `liquidity_anchor`
- `trend_leader`
- `industry_representative`
- `held_exposure`

Missing current constituent detail suppresses leader claims instead of inventing a role.

`market_outlook` requires `short_term` with horizon `1-5 trading days` and `medium_term` with horizon `1-3 months`. Each horizon requires `base_case`, `stronger_case`, `weaker_case`, `key_variables`, `portfolio_posture`, `invalidation`, and `confidence`.

When positions carry exact `cash_unreadable: true` or `total_assets_lower_bound: true`, `portfolio_diagnosis.stock_exposure` and `cash_weight` are unknown. Account analysis normalizes concentration across visible holdings; target research carries finite-positive `visible_account_stock_value` from the full visible source account and uses that denominator instead of renormalizing the requested subset to 100%. Optional `asset_coverage_note` identifies which denominator was used.

Each `holding_analyses[]` item requires `code`, `name`, `account_role`, `industry_panorama`, `mainline_links`, `factor_evidence`, `bull_evidence`, `bear_evidence`, `thesis_status`, `data_confidence`, `evidence_gaps`, `action`, `priority`, `target_weight`, `reason`, `trigger`, `invalidation`, `risk_note`, and `evidence_ids`. Required textual claims are non-empty strings. Priority is an integer from 1 through 5, and target weight is a finite non-boolean JSON number in `[0, 0.15]`; a research-only `watch` item must keep target weight `0`.

`data_coverage` summarizes whether the current run had enough source data to support its conclusions:

- `holdings`
- `quotes`
- `history`
- `fund_flow`
- `events`
- `industry`
- `board_summaries`
- `indices`
- `market_news`
- `errors`

Independent source requests may run concurrently. A source failure must remain visible in `market_data_errors.json` and `data_coverage`; it must not remove successfully collected data for another code.

For compatibility with earlier generated reports, the runner may also include `*_count` aliases such as `holding_count`, `quote_count`, `history_count`, `market_news_count`, and `data_error_count`. Prefer the shorter canonical fields above when writing new consumers.

`market_news_context` summarizes broad weekend/current-market news collected from the market-news feed:

- `count`
- `item_count` as a compatibility alias for `count`
- `top_topics[]` with `topic`, `hits`, and sample titles
- `latest[]` with the most recent visible news titles

Each `stock_scores[]` item should include:

- `code`
- `name`
- `industry`
- `current_weight`
- `scores.total_score`
- `scores.trend_score`
- `scores.macd_score`
- `scores.fund_flow_score`
- `scores.sector_score`
- `scores.event_score`
- `scores.raw`
- `scores.raw.fund_flow_5d_net_wan`
- optional `scores.score_imputations`
- `data_confidence`

With no usable finite fund-flow row, `missing_data` contains `fund_flow`, while `scores.fund_flow_score` and `scores.raw.fund_flow_5d_net_wan` are null. `scores.total_score` may retain the historical threshold scale by internally imputing neutral 50, but then `scores.score_imputations.fund_flow` must be a finite non-boolean number exactly equal to `50.0`; a public fund-flow score and this imputation are mutually exclusive. Legitimate numeric zero remains public evidence, and a ratio-only score may remain public even when the raw five-day net value is null.

The imputation rule is bidirectional: whenever `scores.score_imputations.fund_flow` exists, `missing_data` must contain `fund_flow`, and both `scores.fund_flow_score` and `scores.raw.fund_flow_5d_net_wan` must be null. Whenever holding `factor_evidence.score_imputations.fund_flow` exists, its public `fund_flow_score` and explicit `raw.fund_flow_5d_net_wan` must also be null. Removing the missing-data marker or synchronizing a fabricated raw value across both layers does not make an imputed score valid.

When `stock_scores` is present, the report validator rejects malformed containers and duplicate stock codes. For each matching holding code, `factor_evidence.fund_flow_score`, `factor_evidence.score_imputations.fund_flow`, and `factor_evidence.raw.fund_flow_5d_net_wan` must match the stock-score layer. Both raw layers must explicitly contain `fund_flow_5d_net_wan`; a missing key is not equivalent to an explicit evidence value of null. Missing-history or missing-stock-data rows may keep both public score and imputation absent; Markdown still labels an explicit neutral imputation as insufficient evidence rather than presenting 50 as observed fund flow.

All six public factor scores (`total`, `trend`, `macd`, `fund_flow`, `sector`, and `event`) are finite non-boolean JSON numbers in `[0, 100]`, except that the contract permits a null public fund-flow score under the missing-evidence rules above. When `stock_scores` is present, its code set must equal the holding code set, names and all six factor scores must match their holding layer, and codes must be unique.

Each `portfolio_actions[]` item must include:

- `code`
- `name`
- `action`
- `reason`
- `trigger`
- `invalidation`
- `target_weight`
- `risk_note`

The action code set must exactly match `holding_analyses`, with unique codes. For each code, name, action, reason, trigger, invalidation, target weight, and risk note must match the holding layer. Target weight uses the same finite `[0, 0.15]` contract; strings are not coerced into numbers.

`loop_review` may be present for an account screenshot run. Its `status` is one of `initial`, `unchanged_snapshot`, `reconciled`, or `stale_snapshot`; its share changes are observations from screenshots rather than broker execution confirmations.

`analysis_mode` may be `target_research`. Codes listed in `research_only_codes` are not account holdings and must retain action `watch` with target weight `0`.

Allowed actions:

- `hold`
- `reduce`
- `exit`
- `watch`
- `add_only_if_triggered`

## Market History and Manual Append Rule

Normalized board snapshots are stored at `.stock-loop/market-history/market_snapshots.jsonl`. The account loop appends at most one row per verified trading date, and only after schema validation, report output, and a successful completed new-screenshot run. Duplicate, unchanged, stale, failed-contract, failed-report, failed-persistence, and target-research commands do not append a new market-history row.

Market history is evidence for continuity, not a watcher or scheduler. Target research may read the existing history for context, but it never appends to it and never advances `state/loop_state.json`.

## Command Failure Status

- Exit `6`, status `invalid_report_contract`: schema-v2 validation failed before report publication.
- Exit `7`, status `report_write_failed`: Markdown report output failed.
- Exit `8`, status `persistence_failed`: durable account params/history/state persistence failed or was rolled back.
- Exit `9`, status `recovery_failed`: an unfinished persistence journal could not be safely validated or recovered; the command stops before reading account state/history/params.
- Exit `10`, status `invalid_params`: strategy parameters are missing, malformed, non-finite, or outside the documented safety bounds.
- Exit `11`, status `artifact_write_failed`: a non-report JSON artifact, staged directory publication, or final account-input write failed and was cleaned up or rolled back.

## strategy_params.json

Only these parameter families may be updated automatically:

- moving-average periods: `ma_short`, `ma_long`
- MACD parameters: `macd_fast`, `macd_slow`, `macd_signal`
- signal weights: `weights.trend`, `weights.macd`, `weights.fund_flow`, `weights.sector`, `weights.event`
- score thresholds: `entry_score`, `hold_score`, `reduce_score`
- risk thresholds: `stop_loss_pct`, `take_profit_pct`, `trailing_profit_pct`
- position constraints: `max_holdings`, `max_single_weight`
- friction assumptions: `roundtrip_cost_bps`, `rebalance_cost_bps`

The loop must not automatically add new trading rules, remove risk controls, or relax halt/limit-up/limit-down handling.

## backtest_result.json

Required fields:

- `status`
- `params`
- `start_date`
- `end_date`
- `metrics`
- `equity_curve`
- `trades`

`scope` may be present. A value of `technical_only_diagnostic` means the historical run lacked point-in-time fund-flow, sector, or event inputs, so it is not eligible to promote `strategy_params.json`.

`metrics` must include:

- `total_return_pct`
- `annualized_return_pct`
- `max_drawdown_pct`
- `sharpe`
- `win_rate_pct`
- `profit_loss_ratio`
- `trade_count`
- `turnover`
- `max_single_trade_loss`
- `max_consecutive_losses`

Execution assumptions:

- signal is generated after close on the signal date
- execution uses the next trading day's open
- signal computation may only use rows available on or before the signal date
- missing, zero-open, zero-close, zero-volume, halted, or otherwise untradable rows are skipped for trading; a held position keeps its last valid close for valuation
- default total roundtrip friction is 45 bps
- the portfolio may hold at most 8 stocks by default
- a single stock may not exceed 15% target weight by default

## optimization_YYYY-MM-DD.json

The optimizer should use walk-forward validation:

- train on the earlier window
- validate on the later window
- promote only if sample-out risk-adjusted score improves enough

A candidate may be promoted only when:

- sample-out risk-adjusted score improves by at least 5% or an absolute floor used by the runner
- maximum drawdown does not worsen by more than 10%
- validation trade count is at least 30
- maximum single-trade loss is not materially worse

If a candidate fails any guardrail, keep the previous `strategy_params.json` and explain the rejection in the report.

## Target Research Output

`analyze-targets` atomically publishes an isolated directory under `.stock-loop/analyses/<timestamp>-<codes>/` containing `analysis.md`, `signal.json`, `positions.json`, `market_data_errors.json`, `backtest.json`, and `analysis_manifest.json`. It must not overwrite account loop reports, advance `state/loop_state.json`, or append `.stock-loop/market-history/market_snapshots.jsonl`.
