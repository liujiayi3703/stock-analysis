# Macro Event Digest Workflow

Use this workflow for FOMC, central-bank speeches, policy meetings, CPI/PPI, employment data, fiscal policy, tariffs, sanctions, or other macro events that may affect market risk appetite and sector rotation.

## Inputs

- event name, date, and market scope
- official statement, transcript, projection table, data release, or credible source links
- current market reaction when available: index futures, yields, FX, commodities, sector ETFs, northbound/southbound flows, or A-share sector data

## Procedure

1. Load `references/macro-event-framework.md`.
2. Prefer primary sources:
   - official statement or release
   - transcript or press conference
   - official projection tables or data appendix
   - market prices after the event
3. Build an event snapshot:
   - what changed versus the prior event
   - what stayed unchanged
   - what the market expected before the event
   - what price action implies after the event
4. Extract the expectation gap:
   - policy path: more hawkish, more dovish, or unchanged
   - growth/inflation/liquidity implications
   - first-order sector impact
   - second-order supply-chain impact
5. Classify market regime:
   - risk-on, risk-off, rotation, or wait
   - confidence and missing evidence
6. Feed the result into `macro-sector-scan` or `three-lens-decision` when stock selection is needed.

## Output

```text
Macro Event Digest

Event Snapshot
- source freshness:
- decision/data:
- prior expectation:
- immediate market reaction:

Expectation Gap
- policy:
- liquidity:
- growth:
- inflation:
- confidence:

Market Impact
- broad market:
- sector winners:
- sector losers:
- A-share transmission:

Decision Use
- what to do now:
- what to wait for:
- invalidation:
```

Do not treat speeches or headlines as trade signals until market reaction and data consistency are checked.
