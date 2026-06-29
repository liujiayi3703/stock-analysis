# Data Validation Workflow

Use this before drawing conclusions from market files, API output, copied tables, or user-provided holdings.

## Steps

1. Identify dataset type: holdings, OHLCV, sector, fundamentals, news, fund flow, or mixed.
2. Check required fields using `references/output-schemas.md`.
3. Run bundled validation scripts when CSV files are available.
4. Check freshness: trade date, report period, source timestamp, and market session.
5. Check internal consistency: duplicate keys, negative prices, impossible volumes, missing tickers, mismatched names.
6. Cross-check critical fields against at least one independent source when the conclusion depends on them.
7. Assign a data confidence level: high, medium, low, or unusable.

## Script Usage

```powershell
python skills/a-share-stock-analysis/scripts/validate_holdings_csv.py holdings.csv
python skills/a-share-stock-analysis/scripts/validate_market_dataset.py market.csv --type ohlcv
```

## Stop Conditions

Stop and ask for more data when:

- ticker or date fields are missing
- holdings cannot be matched to securities
- price or volume data is stale for a current-market recommendation
- the user's requested conclusion depends on unverified rumors

## Handoff

Return a validation note:

- usable fields
- rejected fields
- missing fields
- confidence level
- analysis limitations

