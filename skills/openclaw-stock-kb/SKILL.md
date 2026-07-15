---
name: openclaw-stock-kb
description: OpenClaw 股票知识库入口。Use when 用户提到 openclaw-stock-kb、股票策略知识库、新手入门、技术指标、均线、MACD、RSI、布林带、均值回归、动量策略、回测、仓位管理、止损、情绪数据、微博/Twitter 情绪采集，或需要为股票分析/量化策略/监控规则调用 OpenClaw 知识库资料。
---

# OpenClaw Stock KB

## Use

Use this skill as a reference layer for stock strategy knowledge. It wraps the downloaded `freestylefly/openclaw-stock-kb` repository, which is a knowledge base rather than a standalone Codex skill.

Load only the needed reference file:

- Overview and index: `references/kb/README.md`
- Complete examples: `references/kb/examples/complete/dual-ma.md`
- OpenClaw monitor example: `references/kb/examples/openclaw/price-monitor.md`
- Indicators: `references/kb/indicators/trend/ma.md`, `references/kb/indicators/trend/macd.md`, `references/kb/indicators/momentum/rsi.md`, `references/kb/indicators/volatility/bollinger.md`
- Strategies: `references/kb/strategies/mean-reversion/*.md`, `references/kb/strategies/momentum/simple-momentum.md`
- Risk: `references/kb/risk-management/position-sizing/kelly-criterion.md`, `references/kb/risk-management/stop-loss/*.md`
- Sentiment: `references/kb/sentiment/data-collection/*.md`
- Backtesting: `references/kb/tools/backtesting/backtrader.md`

## Guidance

When applying the knowledge base to A-share holdings, adapt rules to available data and China market constraints such as T+1,涨跌停, liquidity, event risk, and sector rotation.

Do not treat examples as trading guarantees. Use them as reusable logic patterns, then validate with current market data.
