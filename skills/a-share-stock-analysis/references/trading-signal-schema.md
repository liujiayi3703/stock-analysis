# A-Share Trading Signal Schema

Use this schema for simulated broker uploads, signal audit files, or strategy output that may become orders.

## Required Columns

| Column | Rule |
|---|---|
| `date` | `YYYY-MM-DD` trading date |
| `time` | `HH:MM:SS` signal time |
| `stock_code` | `000001.SZ`, `600000.SH`, or `430000.BJ` style code |
| `direction` | `BUY` or `SELL` |
| `action` | `OPEN` or `CLOSE` |
| `volume` | positive integer and normally a multiple of 100 shares |
| `price` | non-negative number; `0` means market order or market-like instruction |
| `signal_id` | globally unique idempotency key |

## Recommended Columns

- `strategy`
- `confidence`
- `reason`
- `source`
- `risk_limit`
- `expected_holding_period`

## Idempotency

`signal_id` is the dedupe key. A retry must reuse the same `signal_id`; a new investment decision must use a new `signal_id`.

Duplicate IDs inside a single upload file should be treated as an error unless the user explicitly says the file is a retry/dedupe test.

## A-Share Constraints

- Ordinary buy orders usually use 100-share lots.
- `SELL OPEN` is not valid for ordinary cash accounts; only consider it for explicitly supported margin, securities lending, or simulation contexts.
- Market orders and best-price orders differ by broker and board. Treat `price = 0` as a warning that broker rules must be confirmed.
- Signals around the open, close, earnings, suspension, limit-up, or limit-down events need extra review.

## Audit Trail

Keep:

- original signal file
- validation output
- upload log
- broker response or simulated order IDs
- reconciliation against actual fills or simulated fills

The goal is reliable execution plumbing, not proving the strategy is profitable.
