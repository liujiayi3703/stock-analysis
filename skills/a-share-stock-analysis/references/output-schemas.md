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

## Report Sections

Every market, stock, or portfolio report should include:

- data coverage
- core conclusion
- evidence
- contrary evidence
- risk controls
- next checks

