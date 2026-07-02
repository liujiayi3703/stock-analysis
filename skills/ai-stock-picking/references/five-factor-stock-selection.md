# Five-Factor Stock Selection Framework

Use this framework when the user asks to find promising A-share stocks through value factors, quality factors, financial health, capital behavior, industry growth, policy support, and risk avoidance.

It is a selection and validation framework. It does not replace sector-first reasoning, industry-chain mapping, or source-backed research. Use it to make the company pool and shortlist more disciplined.

## Trigger Phrases

Load this file when the request includes any of these ideas:

- "价值因子和质量因子"
- "最具潜力的股票"
- "确认基本盘"
- "盈利趋势和现金流"
- "近1个月主力资金流向"
- "量比、换手率、委比"
- "行业成长空间"
- "政策支持"
- "规避风险"
- "五步法选股" or "五步分析"

## Five Steps

### 1. Initial Screen: Value + Quality

Goal: build the first candidate pool from measurable value and quality factors.

Value factors:

- PE, PB, PS, EV/EBITDA, dividend yield, free-cash-flow yield when available
- valuation percentile versus the company's own history and sector peers
- valuation matched against growth, margin, ROE, and balance-sheet quality
- avoid "cheap for a reason" names with declining business quality or unresolved governance issues

Quality factors:

- ROE/ROIC level and trend
- gross margin, net margin, and margin stability versus peers
- operating cash flow versus net profit
- asset-liability ratio, interest-bearing debt pressure, and short-term solvency
- receivables, inventory, and working-capital pressure
- moat evidence: pricing power, cost advantage, technology barrier, channel control, brand, regulation barrier, or customer stickiness

Default screen:

- keep companies with at least neutral valuation and above-sector quality
- reject ST, delisting-risk, major governance-risk, and pure concept stocks without earnings or cash-flow evidence
- label each candidate as value-led, quality-led, growth-led, turnaround, or high-risk speculation

### 2. Confirm the Fundamental Base

Goal: test whether the business supports the stock narrative.

Check:

- revenue and net-profit trend across the latest annual, interim, and quarterly reports
- earnings quality: recurring profit, non-recurring gains, impairment, subsidy dependence
- cash-flow direction: operating cash flow, free cash flow, capex intensity, cash conversion
- balance-sheet health: leverage, maturity pressure, liquidity, guarantees, pledges
- peer comparison: whether the company is improving faster or deteriorating slower than peers

Output a verdict: strong base, improving base, mixed base, weak base, or data insufficient.

### 3. Capital Behavior And Market Microstructure

Goal: determine whether recent trading confirms or contradicts the thesis.

Use the latest reliable data for:

- broad A-share market regime and liquidity
- sector and concept strength
- 1-month main-fund flow, northbound/institutional flow where available
- volume ratio, turnover rate, amount, relative volume, and price-volume structure
- order imbalance / 委比 only as intraday auxiliary evidence, never as a standalone reason

Healthy behavior usually means:

- rising or stabilizing price with moderate volume expansion
- sector strength is not only one-day speculation
- fund flow is consistent with price behavior across several sessions
- turnover is active but not extreme enough to imply disorderly speculation

Unhealthy behavior includes:

- price rising while fund flow, sector strength, and volume structure diverge
- repeated high turnover without follow-through
- abnormal spikes caused only by rumor, concept label, or limit-up emotion

### 4. Future Growth And Policy Support

Goal: test whether the company has a real forward runway.

Analyze:

- industry demand growth, capacity cycle, pricing cycle, and replacement cycle
- profit-pool position in the industry chain
- company strategy, product direction, capacity expansion, order visibility, or technology upgrade
- policy support, subsidy dependence, procurement rules, environmental/regulatory constraints
- whether policy creates durable earnings support or only short-term theme attention

Verdict: structural tailwind, cyclical rebound, policy-supported but execution-dependent, neutral, or headwind.

### 5. Risk Avoidance

Goal: identify what can break the thesis or create sharp price volatility.

Risk categories:

- valuation risk: expectation too full, valuation far above growth quality
- business risk: margin compression, weak demand, customer concentration, capacity oversupply
- financial risk: cash-flow deterioration, debt pressure, receivable/inventory expansion
- policy risk: subsidy retreat, regulatory tightening, procurement changes, export controls
- event risk: litigation, pledge, shareholder reduction, audit concern, M&A uncertainty
- trading risk: liquidity collapse, technical breakdown, limit-down/halts, crowded theme unwind

Each shortlisted stock must have at least one invalidation condition and one next check.

## Suggested Scoring

Use scoring only to structure judgment, not as a mechanical buy signal.

| Dimension | Default Weight |
|---|---:|
| Value factors | 20 |
| Quality factors | 25 |
| Fundamental base | 20 |
| Capital behavior | 15 |
| Growth runway and policy support | 20 |
| Risk penalty | -25 to 0 |

Interpretation:

- 80+: eligible for shortlist or deep-dive if data is current and risks are controlled
- 65-79: watchlist or conditional research candidate
- 50-64: keep observing; do not upgrade without new evidence
- below 50: exclude unless user explicitly wants a high-risk turnaround case

## Output Requirements

For each candidate, include:

- ticker and name
- value-factor verdict
- quality-factor verdict
- fundamental-base verdict
- 1-month capital behavior
- growth/policy verdict
- top risks
- total score or qualitative rank
- action framing: exclude, watchlist, deep-dive, conditional trial, or existing-position review
- invalidation condition
- next data check

Always distinguish:

- facts from sources
- inferred thesis
- missing or stale data
- action conditions and risk controls

