# Output Schemas

Use these schemas to normalize files and reports.

## Holdings CSV

Required:

- `ticker`
- `name`

Recommended:

- `exchange`
- `shares`
- `weight`
- `cost_basis`
- `latest_price`
- `holding_thesis`
- `horizon`
- `notes`

Rules:

- At least one of `shares` or `weight` should be present for portfolio-level review.
- `cost_basis` is optional but important for action suggestions.
- Use one row per security.

## OHLCV Dataset

Required:

- `ticker`
- `date`
- `open`
- `high`
- `low`
- `close`
- `volume`

Recommended:

- `amount`
- `adj_factor`
- `exchange`
- `name`
- `sector`

## Sector Hotspot Table

Required:

- `date`
- `sector`
- `return`
- `turnover` or `amount`

Recommended:

- `leader_tickers`
- `limit_up_count`
- `advancer_ratio`
- `catalyst`
- `source`

## Trade Signal CSV

Required:

- `date`
- `time`
- `stock_code`
- `direction`
- `action`
- `volume`
- `price`
- `signal_id`

Rules:

- `stock_code` should use `000001.SZ`, `600000.SH`, or `430000.BJ` style exchange suffixes.
- `direction` must be `BUY` or `SELL`.
- `action` must be `OPEN` or `CLOSE`.
- `volume` must be a positive integer and normally a multiple of 100 shares.
- `price` must be non-negative; `0` means market-order behavior must be confirmed with the broker.
- `signal_id` must be unique for idempotency unless the file is explicitly a retry test.

## Report Sections

Every market, stock, or portfolio report should include:

- data coverage
- core conclusion
- industry panorama cognition for individual stocks or material holdings
- five-factor evidence summary when the request includes value/quality, financial health, fund-flow, growth/policy, or risk-avoidance analysis
- evidence
- contrary evidence
- risk controls
- next checks

## Five-Factor Stock Review

Use this schema for individual-stock or holding analysis when `references/five-factor-stock-selection.md` is loaded.

Required:

- `ticker`
- `name`
- `value_factor`
- `quality_factor`
- `fundamental_base`
- `one_month_funds_trading`
- `growth_policy`
- `key_risks`
- `action`
- `trigger`
- `invalidation`

Recommended:

- `market_regime`
- `sector_context`
- `valuation_note`
- `main_fund_flow_1m`
- `volume_ratio`
- `turnover_rate`
- `order_imbalance`
- `target_weight_or_range`
- `confidence`

Allowed actions:

- `watch`
- `hold`
- `add_only_if_triggered`
- `reduce`
- `exit`

## Industry Panorama Cognition

Use this schema for individual-company analysis and material holdings. Load `references/industry-panorama-template.md` for the detailed checklist.

Required:

- `ticker`
- `name`
- `known_industry_label`
- `segment`
- `value_chain_position`
- `upstream_dependencies`
- `downstream_customers`
- `industry_influence`
- `scarce_capability_or_moat`
- `analogy`
- `unknowns_to_verify`
