# Three-Lens Decision Workflow

Use this workflow when a request needs a fast but complete investment decision review across direction, target quality, and execution timing.

## Inputs

- market and date
- ticker, sector, watchlist, or holding
- horizon: intraday, swing, medium-term, or long-term
- available macro, industry, fundamentals, technicals, and news data

If current market data is required, verify it with fresh sources before analysis.

## Procedure

1. Load `references/three-lens-framework.md`.
2. Build a data snapshot before any conclusion:
   - price, valuation, volume, recent earnings, and guidance
   - macro regime, liquidity, policy direction, and market sentiment
   - industry-chain position, supply-demand gap, and substitution risk
   - technical state: trend, support/resistance, ATR or volatility, volume confirmation
3. Run the macro lens first. Decide whether the environment is tailwind, headwind, or wait.
4. Run the chain lens second. Decide whether the company or sector owns a hard-to-replace node, profit pool, or demand bottleneck.
5. Run the execution lens third. Decide whether current price-volume structure permits action.
6. Force disagreement checks:
   - macro bullish but chain weak: reduce to watchlist or reject
   - chain strong but macro hostile: avoid aggressive sizing
   - macro and chain strong but execution weak: wait for trigger
   - execution strong but evidence weak: classify as momentum-only, not thesis-backed
7. End with an action framing, not an unconditional trade call.

## Output

Use this structure:

```text
Three-Lens Decision

Data Snapshot
- sources and freshness:
- missing data:

Macro Lens
- regime:
- evidence:
- conclusion: tailwind / headwind / wait

Industry-Chain Lens
- chain position:
- bottleneck score:
- demand/supply evidence:
- conclusion: strong / mixed / weak

Execution Lens
- market-day type:
- trend and key levels:
- volume/ATR/volatility confirmation:
- conclusion: actionable / wait / avoid

Disagreement Table
| Lens | Signal | Confidence | What Would Invalidate |

Action Framing
- market-level:
- stock-level:
- position sizing boundary:
- next checks:
```

Always add a risk disclaimer in the user's language.
