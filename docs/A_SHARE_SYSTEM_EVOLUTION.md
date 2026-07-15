# A股持仓分析体系进化说明

本文档用于以后快速恢复和更新当前的持仓分析体系。先读本文件，再进入 `skills/stock-strategy-loop/SKILL.md` 跑每日或周末复盘。

## 目标

当前体系的目标不是自动下单，而是把“最新持仓 + 周末消息 + 市场结构 + 个股资金/事件 + 回测验证”沉淀成可复用的决策支持流程。

输出必须同时回答四件事：

1. 这次结论用了哪些数据，哪些数据缺失。
2. 大盘和板块环境是否支持下周进攻。
3. 每只持仓是持有、观察、减仓、退出，还是只在触发条件成立时加仓。
4. 结论是否被历史回测和参数边界约束过。

## 数据采集层

`stock-strategy-loop` 现在优先收集这些数据：

- 持仓数据：来自 `.stock-loop/positions/positions.json`，可由最新截图人工或视觉抽取后校验。
- 行情数据：个股实时报价、历史 K 线、指数环境。
- 板块数据：行业标签、市场板块热度、行业涨跌。
- 资金数据：主力净流入、主力净占比、超大单和大单净流入，内部统一为稳定字段。
- 事件数据：公告、业绩预告、风险提示、调研、订单、回购、减持等。
- 市场消息：周末或当前市场新闻主题，用于识别 AI 算力、机器人、商业航天、汽车、化工材料、医药、宏观风险等方向的情绪和催化。
- 数据覆盖：`data_coverage` 会记录本次 quotes/history/fund_flow/events/industry/board/index/market_news 的可用数量和错误数。

## 分析层

每只持仓的分数由这些部分组成：

- 趋势结构：短均线、长均线、20/60 日收益、价格相对位置。
- MACD 节奏：DIF/DEA/MACD 柱及拐点状态。
- 资金健康度：最近资金流向和 5 日主力净流入。
- 板块支持：个股行业是否和当前市场板块方向共振。
- 事件偏置：业绩预增、订单、调研、回购等加分；减持、处罚、问询、亏损、风险提示等扣分。
- 数据置信度：关键数据缺失时，自动降级为观察，不生成激进动作。

## 每次运行流程

在仓库根目录或当前持仓工作区中执行：

```powershell
python .\skills\stock-strategy-loop\scripts\run_loop.py --workspace "<workspace>" scan-screenshots
python .\skills\stock-strategy-loop\scripts\run_loop.py validate-positions --positions-json "<workspace>\.stock-loop\positions\positions.json"
python .\skills\stock-strategy-loop\scripts\run_loop.py --workspace "<workspace>" run --include-events --a-share-skill "<path-to-a-share-data-skill>"
```

输出位置：

- `.stock-loop/runs/YYYY-MM-DD/report.md`
- `.stock-loop/runs/YYYY-MM-DD/daily_signal.json`
- `.stock-loop/backtests/backtest_result_YYYY-MM-DD.json`
- `.stock-loop/backtests/optimization_YYYY-MM-DD.json`
- `.stock-loop/params/strategy_params.json`

## 解读顺序

1. 先看 `report.md` 的数据覆盖和数据问题。
2. 再看组合动作，确认每只股票的 trigger 和 invalidation。
3. 再看 `daily_signal.json` 的 `stock_scores[].scores.raw`，尤其是 `fund_flow_5d_net_wan`、`event_bias`、`sector_change_pct`。
4. 最后看回测和优化是否通过样本外约束。若优化被拒绝，继续沿用旧参数。

## 更新清单

升级体系时只做必要改动：

- 新增数据源时，先把字段归一化为内部稳定字段，再进入评分。
- 新增输出字段时，同步更新 `skills/stock-strategy-loop/references/loop-contracts.md`。
- 改交易规则前，先把它写成独立假设，不要直接放宽风控。
- 发布前至少运行 `python -m py_compile skills/stock-strategy-loop/scripts/run_loop.py` 和示例持仓校验。

## 当前限制

- 本体系只做研究和模拟，不自动下单。
- 截图抽取仍依赖人工或视觉模型复核，缺字段时不得编造。
- 周末消息只能作为催化和风险背景，不能替代价格、资金和公告验证。
- 数据接口可能间歇失败，必须看 `data_coverage.errors` 后再决定仓位动作。
