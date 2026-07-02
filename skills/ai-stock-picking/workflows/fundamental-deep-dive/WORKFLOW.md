# Fundamental Deep Dive Workflow

Use this to validate whether screened companies have real business support.

## Steps

1. Read latest annual, quarterly, and interim data where available.
2. Analyze:
   - ROE and drivers
   - revenue growth and quality
   - gross margin and net margin
   - operating cash flow
   - asset-liability ratio and debt maturity
   - inventory, receivables, and working capital pressure
   - capex and order visibility
3. If `references/five-factor-stock-selection.md` is loaded, explicitly classify the fundamental base as strong, improving, mixed, weak, or data insufficient.
4. Compare company metrics with sector peers.
5. Check whether the company benefits from the selected profit-pool link.
6. Use specialist skills when relevant:
   - `tam-adj-peg` for growth valuation
   - `bayesian-intrinsic-growth-valuation` for 3-5 year intrinsic growth
   - `buy-side-equity-research-memo` for full company memo

## Output

| Ticker | Profit trend | Cash-flow direction | Growth quality | Margin quality | Leverage risk | Moat/pricing power | Fundamental-base verdict |
|---|---|---|---|---|---|---|---|

## Handoff

Return:

- pass/fail/watch verdict
- evidence supporting the verdict
- financial red flags
- candidates for `technical-assist`

