# Positions JSON Schema

`positions.json` is the bridge between Codex visual extraction and the deterministic strategy runner.

## Required top-level fields

```json
{
  "snapshot_time": "2026-07-01 21:15:40",
  "source_screenshots": ["absolute image path"],
  "accounts": [],
  "holdings": [],
  "cash": 139564.84,
  "stock_value": 604068.0,
  "total_assets": 743632.84
}
```

## Required holding fields

```json
{
  "account": "account_1",
  "code": "605020",
  "name": "永和股份",
  "shares": 1900,
  "cost_price": 39.796,
  "last_price": 43.99,
  "market_value": 83581,
  "unrealized_pnl": 7968.39
}
```

## Extraction rules

- Use screenshot filename time as `snapshot_time`.
- Preserve one row per visible holding.
- Use numbers exactly as shown in the screenshot.
- If market value is not visible but shares and last price are visible, calculate it and mark `market_value_derived: true`.
- If a required field is unreadable, stop and report the missing field instead of guessing.
- Validate that `sum(holding.market_value)` is close to top-level `stock_value`.
- Validate that `stock_value + cash` is close to `total_assets`.

## Notes

- Codes must be six-digit A-share codes.
- Costs and prices are yuan per share.
- `unrealized_pnl` is yuan, not percent.
- Percent fields can be added, but the runner does not require them.

