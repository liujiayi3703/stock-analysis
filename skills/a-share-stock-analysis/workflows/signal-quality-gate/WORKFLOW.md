# Signal Quality Gate Workflow

Use this workflow when the user provides trade signals, simulated broker instructions, or a CSV that may become orders.

## Inputs

- signal CSV path or pasted table
- intended account type: cash, margin, or simulation
- market session and date
- whether duplicate `signal_id` rows are expected test cases

## Procedure

1. Load `references/trading-signal-schema.md`.
2. If a CSV file is available, run:

```powershell
python scripts/validate_trade_signals.py path\to\signals.csv
```

Use `--json` when another tool needs machine-readable output.

3. Review hard errors:
   - missing required columns
   - invalid A-share code format
   - invalid direction or action
   - non-positive or non-lot-size volume
   - negative price
   - duplicate or empty signal ID
   - invalid date or time
4. Review warnings:
   - market-order price `0`
   - `SELL OPEN` on ordinary A-share cash account
   - large repeated ticker concentration
   - signals near session open or event windows
5. Decide whether the file is:
   - accepted for simulation
   - accepted only after broker/account constraints are confirmed
   - rejected until fixed
6. If accepted, create an audit summary using `templates/trading-signal-audit.md`.

## Output

Include:

- validation result: pass / pass with warnings / fail
- row count and unique signal count
- errors and warnings
- duplicate handling
- risk controls before upload
- reconciliation plan after execution

Never treat a valid CSV as an investment recommendation. It only means the instruction file is structurally safe enough for the next stage.
