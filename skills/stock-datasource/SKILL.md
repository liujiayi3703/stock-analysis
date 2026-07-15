---
name: stock-datasource
description: stock_datasource 总入口与路由 skill。Use when 用户提到 stock_datasource、stock-datasource、stock_datasource 数据源、股票数据源、实时订阅、行情推送、MCP 股票查询、Tushare 插件构建、API key 鉴权、stock-mcp-query、stock-rt-subscribe、stock-data-assistant、tushare-plugin-builder，或需要把量化交易/监控系统的数据源能力接入股票分析。
---

# Stock Datasource Router

## Use

Use this as the entry point for the downloaded `Yourdaylight/stock_datasource` skill set. The repository contains multiple focused skills that have been installed separately.

Route by task:

- Stock data query through MCP: use `stock-mcp-query`.
- Realtime subscription and alert workflow: use `stock-rt-subscribe`.
- Data assistant and PicoClaw config: use `stock-data-assistant`.
- Tushare plugin development: use `tushare-plugin-builder`.
- API key authentication for MCP tools: use `mcp-api-key-auth`.

## Notes

Load `references/installed-map.md` when you need the exact installed skill map and source repository.

Keep analysis outputs evidence-based. If a data source is unavailable or credentials are missing, state the limitation and fall back to other installed A-share data skills where appropriate.
