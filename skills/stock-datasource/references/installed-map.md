# stock_datasource Installed Map

Source repository: `Yourdaylight/stock_datasource`

Installed sub-skills:

| Installed skill | Source path | Primary use |
| --- | --- | --- |
| `mcp-api-key-auth` | `skills/mcp-api-key-auth` | API key authentication for MCP services |
| `stock-data-assistant` | `skills/stock-data-assistant` | Stock data assistant workflow and PicoClaw setup |
| `stock-mcp-query` | `skills/stock-mcp-query` | Query stock data through MCP interfaces |
| `stock-rt-subscribe` | `skills/stock-rt-subscribe` | Realtime subscription, strategy alert, and push workflows |
| `tushare-plugin-builder` | `skills/tushare-plugin-builder` | Build and validate Tushare data plugins |

Suggested routing:

- Ask for market data or structured stock query: `stock-mcp-query`
- Ask for realtime monitoring, alerting, or push: `stock-rt-subscribe`
- Ask for data pipeline/plugin extension: `tushare-plugin-builder`
- Ask for setup/configuration: `stock-data-assistant`
- Ask about credentials: `mcp-api-key-auth`
