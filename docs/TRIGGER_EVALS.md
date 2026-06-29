# Trigger Evals

Use these prompts to smoke-test whether an agent selects the skill and routes to the right workflow.

| Eval ID | Prompt | Expected Route |
|---|---|---|
| market-hotspots | 今天A股有哪些主线热点？帮我从成交额、涨停、板块强度和新闻催化里验证。 | `market-hotspots` plus `data-validation` |
| market-risk | 帮我判断现在大盘环境适不适合加仓，给出证据和风险边界。 | `market-analysis` then `recommendation` |
| stock-analysis | 分析一下 600519 的趋势、基本面、资金和风险，给我操作建议。 | `stock-analysis` then `recommendation` |
| portfolio-review | 这是我的持仓表，帮我看哪些要加、减、留、观察。 | `portfolio-review` then `recommendation` |
| data-check | 我有一份A股行情CSV，先检查数据是否可信，再决定能不能分析。 | `data-validation` |

Passing behavior:

- The agent reads `SKILL.md` first.
- The agent does not skip data validation when evidence is missing or file quality is unknown.
- The agent separates facts, inference, uncertainty, and suggestions.
- The agent gives invalidation conditions and risk controls with any trading suggestion.

