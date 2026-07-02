# Third-Party Source Notes

This repository may learn from public materials, but it should remain a clean, reusable skill library. Do not copy third-party text or code unless licensing allows it and attribution is preserved.

## Sources Reviewed

| Source | Public Status | License | How It Was Used |
|---|---|---|---|
| [destiny520537work-lab/fate-skill](https://github.com/destiny520537work-lab/fate-skill) | public GitHub repository | MIT | Learned the three-lens market-analysis pattern: macro direction, supply-chain bottleneck, execution discipline. The implementation here is rewritten and generalized for this repository. |
| [destiny520537work-lab/stock-research](https://github.com/destiny520537work-lab/stock-research) | public GitHub repository | no license detected | Used only as conceptual inspiration for source-backed research: broker fundamentals, historical valuation, target-price scenarios, and separate stop-loss logic. No text or code copied. |
| [destiny520537work-lab/work-lab](https://github.com/destiny520537work-lab/work-lab) | public GitHub repository | no license detected | Used only as conceptual inspiration for trade-signal quality gates: schema validation, idempotent `signal_id`, retry safety, logging, and reconciliation. No text or code copied. |
| [destiny520537work-lab/warsh-first-fomc-press-conference-2026](https://github.com/destiny520537work-lab/warsh-first-fomc-press-conference-2026) | public GitHub repository | no license detected | Used only as conceptual inspiration for macro-event digestion: primary-source review, expectation gaps, and market reaction checks. No transcript text copied. |

## User-Provided Frameworks

| Framework | Source | How It Was Used |
|---|---|---|
| Five-factor stock selection and operation review | User-provided requirements in this repository workflow | Converted into reusable skill references for value factors, quality factors, financial-base confirmation, 1-month capital behavior, growth/policy support, and risk avoidance. |
| Stock strategy loop | User-provided implementation plan in this repository workflow | Converted into the `stock-strategy-loop` orchestrator for screenshot holdings, market analysis, strategy generation, 3-year strict backtesting, bounded parameter optimization, and Markdown/JSON outputs. |

## Reuse Rules

- MIT-licensed ideas can be adapted with attribution.
- No-license repositories are treated as read-only learning sources; rewrite concepts in original words and do not copy files.
- For market data, policy, earnings, rules, and prices, agents must verify current facts from fresh sources before analysis.
- Every output remains decision support, not guaranteed investment advice.
