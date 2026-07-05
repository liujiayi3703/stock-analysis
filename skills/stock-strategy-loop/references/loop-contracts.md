# Stock Strategy Loop Contracts

These contracts define the durable JSON interfaces used by `scripts/run_loop.py`.

## Runtime Directories

The runner creates these folders under the selected workspace:

```text
.stock-loop/
  positions/
  runs/YYYY-MM-DD/
  backtests/
  params/
  cache/
```

Do not treat `.stock-loop/` as source code. It is a local runtime state directory for portfolio snapshots, reports, backtests, and parameter versions.

## daily_signal.json

Required top-level fields:

```json
{
  "generated_at": "2026-07-03 21:00:00",
  "snapshot_time": "2026-07-03 20:58:00",
  "data_coverage": {},
  "market_regime": {},
  "market_news_context": {},
  "sector_context": {},
  "stock_scores": [],
  "portfolio_actions": []
}
```

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

`market_news_context` summarizes broad weekend/current-market news collected from the market-news feed:

- `count`
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
- `data_confidence`

Each `portfolio_actions[]` item must include:

- `code`
- `name`
- `action`
- `reason`
- `trigger`
- `invalidation`
- `target_weight`
- `risk_note`

Allowed actions:

- `hold`
- `reduce`
- `exit`
- `watch`
- `add_only_if_triggered`

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
- missing, zero-open, zero-close, zero-volume, halted, or otherwise untradable rows are skipped
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
