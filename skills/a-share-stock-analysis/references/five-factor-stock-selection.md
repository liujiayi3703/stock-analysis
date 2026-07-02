# Five-Factor A-Share Stock Review

Use this framework when the user asks for a comprehensive A-share stock or holding analysis using value factors, quality factors, financial health, capital flow, industry growth, policy support, and risk avoidance.

This is an operation-support framework for a known stock, watchlist, or current holding. It should be combined with market analysis, data validation, stock analysis, portfolio review, and recommendation workflows.

## Trigger Phrases

Load this file when the request includes any of these ideas:

- "价值因子和质量因子"
- "最具潜力的股票"
- "确认基本盘"
- "财务健康程度"
- "盈利趋势和现金流走向"
- "近1个月主力资金流向"
- "量比、换手率、委比"
- "行业成长空间"
- "政策支持"
- "规避风险"
- "哪些因素可能会导致股价波动"
- "五步法分析" or "五步操作分析"

## Required Data

Use fresh sources where possible. If a field is unavailable, mark it as missing instead of guessing.

- price/volume: OHLCV, amount, relative strength, limit-up/limit-down status
- market context: major indices, risk appetite, liquidity, active sectors/themes
- fundamentals: latest annual, interim, quarterly data, margins, ROE, leverage, cash flow
- valuation: PE, PB, PS, dividend yield, historical percentile, sector percentile where available
- capital behavior: 1-month main-fund flow, turnover rate, volume ratio, order imbalance / 委比 if intraday data is reliable
- industry/policy: sector cycle, demand, supply, policy documents, subsidy/regulatory exposure
- events: earnings pre-announcement, pledge/reduction, litigation, M&A, abnormal announcements

## Five-Step Review

### 1. Initial Screen: Value + Quality

Classify the stock as value-led, quality-led, growth-led, turnaround, defensive, or high-risk speculation.

Value checks:

- valuation versus peers and own history
- valuation versus growth, margin quality, cash-flow quality, and policy cycle
- dividend or free-cash-flow support if relevant

Quality checks:

- ROE/ROIC trend
- margin level and stability
- operating cash flow versus net profit
- leverage, receivables, inventory, and working-capital pressure
- moat or bargaining-power evidence

### 2. Confirm the Fundamental Base

Assess whether the company's business condition supports the trading thesis.

Focus on:

- revenue and net-profit trend
- profitability trend and margin drivers
- cash-flow direction and cash conversion
- balance-sheet pressure
- earnings quality and non-recurring gains
- peer comparison

Verdict: strong base, improving base, mixed base, weak base, or data insufficient.

### 3. Capital Flow And Trading Health

Analyze the latest 1-month trading evidence:

- main-fund flow direction and persistence
- volume ratio and relative volume
- turnover rate level and whether it matches the stock's style
- order imbalance / 委比 only as intraday auxiliary evidence
- price-volume structure, support/resistance, relative strength versus sector
- whether broad market and sector conditions support the stock's move

Do not let one-day fund flow or 委比 override fundamentals, trend, and risk controls.

### 4. Growth Space And Policy Support

Assess:

- industry growth runway and demand cycle
- company's position in the industry chain and profit pool
- product, capacity, order, technology, or channel direction
- policy support, regulation, procurement, subsidy, localization, export-control exposure
- whether policy support can translate into revenue, margin, or cash flow

Verdict: structural tailwind, cyclical rebound, policy-supported but execution-dependent, neutral, or headwind.

### 5. Risk Avoidance

List specific volatility triggers:

- valuation compression
- weak earnings, margin decline, or cash-flow deterioration
- customer concentration, capacity oversupply, or price competition
- policy change, subsidy withdrawal, regulatory tightening, or export restriction
- pledge/reduction/litigation/audit/M&A event risk
- technical breakdown, liquidity drop, crowded theme unwind, limit-down/halts

Every operation suggestion must include:

- trigger: what must happen before acting
- invalidation: what proves the view wrong
- risk note: position size, stop-loss, review date, or data that must be refreshed

## Operation Mapping

Use these action labels unless the user asks for a different format:

| Evidence State | Suggested Framing |
|---|---|
| value/quality/fundamental base all strong, capital behavior confirms, risks controlled | `add only if triggered` or `hold` |
| fundamentals acceptable but capital behavior weak or market regime poor | `hold` or `watch` |
| valuation stretched, capital flow diverges, or risk event unresolved | `reduce` |
| fundamental base breaks or invalidation condition is met | `exit` |
| data is stale, contradictory, or missing key fields | `watch` with low confidence |

Do not output unconditional "must buy" or "must sell". Use conditional suggestions and separate evidence from inference.

## Output Table

For each stock, include:

| Stock | Value factor | Quality factor | Fundamental base | 1-month funds/trading | Growth/policy | Key risks | Action | Trigger | Invalidation |
|---|---|---|---|---|---|---|---|---|---|

For portfolio review, add:

- current weight or market value
- role: core, satellite, trade, hedge, watch, or error position
- target weight range
- priority: urgent, normal, or monitor

