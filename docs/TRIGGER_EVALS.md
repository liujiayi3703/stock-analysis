# Trigger Evals

Use these prompts to smoke-test whether an agent selects the right skill and routes to the right workflow.

| Eval ID | Prompt | Expected Route |
|---|---|---|
| ai-stock-picking-full | 帮我用AI选股：先找未来6-12个月值得关注的赛道，再拆产业链，最后筛出高增长、高利润率、高议价权的公司。 | `ai-stock-picking` full pipeline |
| sector-first | 不要直接给股票，先帮我判断钱可能流向哪些行业，再从产业链里找公司。 | `ai-stock-picking` -> `macro-sector-scan` then `industry-chain-map` |
| three-high-screen | 在新能源/AI/机器人产业链里筛选三高公司：高增长、高利润率、高议价权，同时排除ST和蹭概念没业绩的票。 | `ai-stock-picking` -> `company-screening` and `thesis-validation` |
| fundamental-technical-validation | 对初筛股票池做基本面深挖和技术面辅助，重点看ROE、现金流、负债率、趋势、支撑压力和MACD/RSI。 | `ai-stock-picking` -> `fundamental-deep-dive` then `technical-assist` |
| three-lens-decision | 三个视角一起看：先判断宏观顺逆风，再看产业链卡点，最后看今天能不能执行。 | `ai-stock-picking` -> `three-lens-decision` |
| source-backed-research | 帮我对这只股票做完整研报：数据来源、历史估值区间、三情景目标价、止损价、入场计划都要有。 | `ai-stock-picking` -> `source-backed-research` |
| macro-event-digest | 这次FOMC/政策会议对A股和科技成长股意味着什么？请看官方文本、预期差和市场反应。 | `ai-stock-picking` -> `macro-event-digest` |
| market-hotspots | 今天A股有哪些主线热点？帮我从成交额、涨停、板块强度和新闻催化里验证。 | `a-share-stock-analysis` -> `market-hotspots` plus `data-validation` |
| market-risk | 帮我判断现在大盘环境适不适合加仓，给出证据和风险边界。 | `a-share-stock-analysis` -> `market-analysis` then `recommendation` |
| stock-analysis | 分析一下 600519 的趋势、基本面、资金和风险，给我操作建议。 | `a-share-stock-analysis` -> `stock-analysis` then `recommendation` |
| portfolio-review | 这是我的持仓表，帮我看哪些要加、减、留、观察。 | `a-share-stock-analysis` -> `portfolio-review` then `recommendation` |
| data-check | 我有一份A股行情CSV，先检查数据是否可信，再决定能不能分析。 | `a-share-stock-analysis` -> `data-validation` |
| signal-quality-gate | 我有一份A股交易信号CSV，先检查能不能安全上传或模拟执行，重点看重复signal_id和100股一手。 | `a-share-stock-analysis` -> `signal-quality-gate` |
| serenity-alpha-news | 这条产业新闻会带来哪些小市值受益股？请按 news -> demand -> financial statements -> validation path 找 alpha。 | `serenity-alpha` |
| bayesian-growth | 用贝叶斯内生成长估值框架看这家公司 3-5 年真实增长是否被市场充分定价。 | `bayesian-intrinsic-growth-valuation` |
| gf-dma-score | 帮我给这只股票做 GF-DMA Health Index，判断上涨趋势是否有基本面支撑以及是否有逃逸风险。 | `gf-dma-health-index` |
| tam-adj-peg | 这只成长股估值贵不贵？请用 TAM-Adj-PEG 看增长速度、增长空间和质量因子。 | `tam-adj-peg` |
| buy-side-memo | 给我写一份买方风格个股深度研究 memo，包含目标价情景、催化剂、风险和监控指标。 | `buy-side-equity-research-memo` |

## Five-Factor Trigger Evals

| Eval ID | Prompt | Expected Route |
|---|---|---|
| five-factor-potential-screen | 通过价值因子和质量因子，帮我找到目前国内股市中最具潜力的股票，并继续检查基本盘、资金动向、行业政策和风险。 | `ai-stock-picking` -> `company-screening` plus `references/five-factor-stock-selection.md`, then `fundamental-deep-dive` and `shortlist-ranking` |
| five-factor-stock-operation | 用价值质量、基本盘、近1个月主力资金、量比换手率委比、行业成长政策和风险五步法分析 605020，并给出条件化操作策略。 | `a-share-stock-analysis` -> `stock-analysis` plus `references/five-factor-stock-selection.md`, then `recommendation` |
| five-factor-holdings-review | 这是我的持仓表，请按价值因子、质量因子、基本盘、资金动向、成长政策和风险逐只分析，再给出持有、减仓、退出或触发加仓条件。 | `a-share-stock-analysis` -> `portfolio-review` plus `references/five-factor-stock-selection.md`, then `recommendation` |

## Strategy Loop Trigger Evals

| Eval ID | Prompt | Expected Route |
|---|---|---|
| stock-loop-latest-screenshots | 下载并分析今日截图，按最新截图识别持仓，形成市场分析、策略、三年回测、参数优化和报告。 | `stock-strategy-loop` -> scan screenshots, require/validate `positions.json`, then run loop |
| stock-loop-existing-positions | 用已有 `.stock-loop/positions/positions.json` 直接跑一次闭环，不自动下单，输出 daily_signal、backtest_result 和 Markdown 报告。 | `stock-strategy-loop` -> validate positions, run market/data/backtest/optimization |
| stock-loop-method-audit | 检查我的股票 skills 如何自动形成“分析市场 -> 生成策略 -> 模拟验证 -> 根据结果自我迭代优化”的闭环。 | `stock-strategy-loop` -> explain loop contracts, backtest assumptions, and optimization guardrails |

Passing behavior:

- The agent reads the selected `SKILL.md` first.
- The agent does not skip data validation when evidence is missing or file quality is unknown.
- The agent separates facts, inference, uncertainty, and suggestions.
- The agent gives invalidation conditions and risk controls with any trading suggestion.
- The agent loads the five-factor reference when the prompt mentions value factors, quality factors, financial health, 1-month capital flow, volume ratio, turnover, order imbalance, policy support, or risk avoidance.
- The agent routes screenshot-based holding loops, strict 3-year backtests, and bounded self-iteration requests to `stock-strategy-loop`.
- The agent treats no-license third-party sources as conceptual input only and does not copy their text or code.
