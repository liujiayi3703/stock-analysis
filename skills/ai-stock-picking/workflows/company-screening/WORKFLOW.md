# Company Screening Workflow

Use this to build the initial stock pool from selected industry-chain links.

## Steps

1. Create the company universe from selected sector links.
2. Apply hard exclusions from `references/red-flag-checklist.md`.
3. Apply quantitative filters from `references/screening-factors.md`.
4. Prefer "three-high" companies:
   - high growth
   - high or improving profit margin
   - high bargaining power or moat
5. Keep both leaders and small pure-play beneficiaries, but label their risk type.
6. Produce an initial pool with evidence and missing fields.

## Suggested Initial Filters

Use these as defaults unless the user provides stricter rules:

- exclude ST, delisting-risk, major unresolved governance-risk companies
- revenue or net profit growth positive over the latest comparable period
- operating cash flow not persistently negative without a clear reason
- debt risk acceptable for the sector
- valuation not obviously detached from growth without catalyst support
- recent volume is not purely abnormal speculation without fundamental evidence

## Handoff

Return:

- included companies
- excluded companies and reason
- missing data by ticker
- candidates for `fundamental-deep-dive`

