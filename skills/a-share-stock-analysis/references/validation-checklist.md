# Validation Checklist

Use this before analysis or recommendations.

## File Checks

- Can the file be opened with UTF-8 or a known encoding?
- Are headers present and unique?
- Are required columns present?
- Are dates parseable?
- Are ticker formats consistent?
- Are numeric fields numeric?
- Are duplicate key rows expected?

## Market Data Checks

- `high >= max(open, close, low)`
- `low <= min(open, close, high)`
- price fields are positive
- volume is non-negative
- date is a trading date or explicitly marked otherwise
- adjustment status is clear for historical price comparisons

## Holdings Checks

- ticker and name exist
- shares and weight are not both missing
- shares, weight, cost basis, and latest price are non-negative
- weights sum to a plausible range when provided
- duplicated tickers are merged or explained

## Source Checks

- source is named
- retrieval timestamp exists for current data
- report period exists for fundamentals
- important catalysts are verifiable
- conflicting sources are noted

## Confidence Levels

| Level | Meaning |
|---|---|
| High | required fields complete, fresh, internally consistent, critical points cross-checked |
| Medium | usable with minor gaps or single-source dependency |
| Low | stale, incomplete, or hard to cross-check |
| Unusable | missing required fields or internally contradictory |

