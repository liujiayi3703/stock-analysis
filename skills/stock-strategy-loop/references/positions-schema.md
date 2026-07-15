# Positions JSON Schema

`positions.json` is the bridge between Codex visual extraction and the deterministic strategy runner.

## Required top-level fields

```json
{
  "snapshot_time": "2026-01-02 15:00:00",
  "source_screenshots": ["screenshots/demo_positions_2026-01-02-15-00-00.png"],
  "accounts": [],
  "holdings": [],
  "cash": 400.0,
  "stock_value": 1600.0,
  "total_assets": 2000.0
}
```

## Required holding fields

```json
{
  "account": "demo_account",
  "code": "000101",
  "name": "示例科技",
  "shares": 100,
  "cost_price": 8.0,
  "last_price": 10.0,
  "market_value": 1000.0,
  "unrealized_pnl": 200.0
}
```

## Extraction rules

- Use screenshot filename time as `snapshot_time`.
- Preserve one row per visible holding.
- Use numbers exactly as shown in the screenshot.
- `shares`, `cost_price`, `last_price`, `market_value`, and `unrealized_pnl` must be finite JSON numbers decoded as built-in integers or floats; booleans, numeric strings such as `"100"`, arrays, objects, `NaN`, and infinities are invalid. Shares, last price, and market value must be positive; cost price must be non-negative.
- If market value is not visible but valid positive shares and last price are visible, omit `market_value`, calculate it, and mark the exact boolean `market_value_derived: true`. The marker does not repair a present malformed market value, and string/numeric lookalikes do not authorize derivation.
- If a required holding field is unreadable, stop and report the missing field instead of guessing.
- If cash or total assets are unreadable, set the corresponding exact boolean marker `cash_unreadable: true` or `total_assets_lower_bound: true`; non-boolean lookalikes do not activate incomplete-asset mode.
- `stock_value` must otherwise be a finite positive JSON number, `cash` a finite non-negative JSON number, and `total_assets` a finite positive JSON number under the same no-boolean/no-string rule. The validator does not replace malformed or missing top-level values with holding sums.
- Exact `cash_unreadable: true` normalizes cash to zero for deterministic arithmetic while keeping exposure unknown. Exact `total_assets_lower_bound: true` normalizes total assets to validated stock value as a visible lower bound.
- For target research from such an incomplete account, the runner derives `visible_account_stock_value` from all finite positive visible holding market values and preserves it as the concentration denominator.
- Validate that `sum(holding.market_value)` is close to top-level `stock_value`.
- Validate that `stock_value + cash` is close to `total_assets`.

## Notes

- Codes must be six-digit A-share codes.
- Costs and prices are yuan per share.
- `unrealized_pnl` is yuan, not percent.
- Percent fields can be added, but the runner does not require them.
