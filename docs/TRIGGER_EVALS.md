# Trigger Evals

Use these prompts to smoke-test whether an agent selects the right skill and routes to the right workflow.

| Eval ID | Prompt | Expected Route |
|---|---|---|
| market-hotspots | 今天A股有哪些主线热点？帮我从成交额、涨停、板块强度和新闻催化里验证。 | `a-share-stock-analysis` -> `market-hotspots` plus `data-validation` |
| market-risk | 帮我判断现在大盘环境适不适合加仓，给出证据和风险边界。 | `a-share-stock-analysis` -> `market-analysis` then `recommendation` |
| stock-analysis | 分析一下 600519 的趋势、基本面、资金和风险，给我操作建议。 | `a-share-stock-analysis` -> `stock-analysis` then `recommendation` |
| portfolio-review | 这是我的持仓表，帮我看哪些要加、减、留、观察。 | `a-share-stock-analysis` -> `portfolio-review` then `recommendation` |
| data-check | 我有一份A股行情CSV，先检查数据是否可信，再决定能不能分析。 | `a-share-stock-analysis` -> `data-validation` |
| serenity-alpha-news | 这条产业新闻会带来哪些小市值受益股？请按 news -> demand -> financial statements -> validation path 找 alpha。 | `serenity-alpha` |
| bayesian-growth | 用贝叶斯内生成长估值框架看这家公司 3-5 年真实增长是否被市场充分定价。 | `bayesian-intrinsic-growth-valuation` |
| gf-dma-score | 帮我给这只股票做 GF-DMA Health Index，判断上涨趋势是否有基本面支撑以及是否有逃逸风险。 | `gf-dma-health-index` |
| tam-adj-peg | 这只成长股估值贵不贵？请用 TAM-Adj-PEG 看增长速度、增长空间和质量因子。 | `tam-adj-peg` |
| buy-side-memo | 给我写一份买方风格个股深度研究 memo，包含目标价情景、催化剂、风险和监控指标。 | `buy-side-equity-research-memo` |

Passing behavior:

- The agent reads the selected `SKILL.md` first.
- The agent does not skip data validation when evidence is missing or file quality is unknown.
- The agent separates facts, inference, uncertainty, and suggestions.
- The agent gives invalidation conditions and risk controls with any trading suggestion.
