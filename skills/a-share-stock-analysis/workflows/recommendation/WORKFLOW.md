# Recommendation Workflow

Use this only after enough data has been validated and an analysis workflow has produced evidence.

## Steps

1. Restate the decision context: market, stock, portfolio, horizon, and risk tolerance.
2. Summarize validated evidence.
3. If `references/five-factor-stock-selection.md` was used, summarize value/quality, fundamental base, capital behavior, growth/policy, and risk-avoidance verdicts before choosing an action.
4. Summarize contrary evidence and unknowns.
5. Choose a suggestion type:
   - observe
   - hold
   - add conditionally
   - reduce conditionally
   - avoid
   - rebalance
6. Attach risk controls:
   - position sizing or exposure range
   - invalidation condition
   - review trigger
   - time horizon
7. State what new data would change the suggestion.

## Suggestion Format

```text
结论：...
适用前提：...
证据：...
反证/风险：...
操作建议：...
失效条件：...
下一步观察：...
```

## Guardrails

- Do not imply certainty.
- Do not recommend all-in or unlimited averaging down.
- Do not ignore stale or unvalidated data.
- Do not use rumors as decisive evidence.
- Do not hide missing data.
- Do not let a single value, quality, fund-flow, or policy signal override the full evidence set.

