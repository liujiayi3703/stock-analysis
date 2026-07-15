# OpenClaw Agent 股价监控示例

## 概述

使用 OpenClaw Agent 定时监控股票价格，当价格达到设定条件时发送提醒。

## 完整代码

```python
# price_monitor.py
import requests
import os
from datetime import datetime

def get_stock_price(symbol):
    """获取股票实时价格"""
    # 使用 Yahoo Finance API
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        price = data['chart']['result'][0]['meta']['regularMarketPrice']
        prev_close = data['chart']['result'][0]['meta']['previousClose']
        change_pct = (price - prev_close) / prev_close * 100
        
        return {
            'price': price,
            'change_pct': change_pct,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    except Exception as e:
        return {'error': str(e)}

def check_price_alerts(symbol, alerts):
    """
    检查价格是否触发警报
    
    alerts格式: {
        'above': 150.0,  # 高于此价格报警
        'below': 120.0,  # 低于此价格报警
        'change_pct': 5.0  # 涨跌幅超过此值报警
    }
    """
    data = get_stock_price(symbol)
    
    if 'error' in data:
        return {'triggered': False, 'error': data['error']}
    
    triggered = False
    messages = []
    
    # 检查上限
    if 'above' in alerts and data['price'] > alerts['above']:
        triggered = True
        messages.append(f"🚀 {symbol} 突破 {alerts['above']}，当前 {data['price']}")
    
    # 检查下限
    if 'below' in alerts and data['price'] < alerts['below']:
        triggered = True
        messages.append(f"📉 {symbol} 跌破 {alerts['below']}，当前 {data['price']}")
    
    # 检查涨跌幅
    if 'change_pct' in alerts and abs(data['change_pct']) > alerts['change_pct']:
        triggered = True
        direction = "📈 大涨" if data['change_pct'] > 0 else "📉 大跌"
        messages.append(f"{direction} {data['change_pct']:.2f}%")
    
    return {
        'triggered': triggered,
        'messages': messages,
        'data': data
    }

# OpenClaw 集成
def send_openclaw_alert(message, channel="#alerts"):
    """发送 OpenClaw 消息"""
    import subprocess
    
    cmd = f'openclaw message send --channel "{channel}" --message "{message}"'
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    return result.returncode == 0

# 主监控循环
def monitor_stocks(watchlist):
    """
    监控股票列表
    
    watchlist格式:
    {
        'AAPL': {'above': 180, 'change_pct': 5},
        'TSLA': {'below': 200, 'change_pct': 8},
        'BABA': {'above': 100, 'below': 80}
    }
    """
    results = []
    
    for symbol, alerts in watchlist.items():
        result = check_price_alerts(symbol, alerts)
        
        if result['triggered']:
            for msg in result['messages']:
                print(f"[{datetime.now()}] ALERT: {msg}")
                send_openclaw_alert(msg)
        
        results.append({
            'symbol': symbol,
            'price': result['data']['price'] if 'data' in result else None,
            'triggered': result['triggered']
        })
    
    return results

# 使用示例
if __name__ == "__main__":
    watchlist = {
        'AAPL': {'above': 190.0, 'change_pct': 3.0},
        'TSLA': {'below': 180.0, 'change_pct': 5.0},
        'NVDA': {'above': 500.0, 'change_pct': 4.0}
    }
    
    monitor_stocks(watchlist)
```

## OpenClaw Cron 定时任务

```bash
# 每5分钟监控一次
openclaw cron add --name "price-monitor" \
  --schedule "*/5 * * * *" \
  --command "python3 /path/to/price_monitor.py"
```

## 高级功能：多条件监控

```python
def advanced_monitor(symbol, conditions):
    """
    多条件监控
    
    conditions: {
        'price_targets': [150, 160, 170],
        'volume_spike': 2.0,  # 成交量放大2倍
        'rsi_extreme': {'above': 70, 'below': 30}
    }
    """
    # 获取完整数据
    price_data = get_stock_price(symbol)
    volume_data = get_volume_data(symbol)
    rsi = calculate_rsi(symbol)
    
    alerts = []
    
    # 检查价格目标
    for target in conditions.get('price_targets', []):
        if abs(price_data['price'] - target) / target < 0.01:  # 1%范围内
            alerts.append(f"{symbol} 接近目标价 {target}")
    
    # 检查成交量
    if volume_data['today'] > volume_data['avg_20d'] * conditions.get('volume_spike', 2):
        alerts.append(f"{symbol} 成交量异常放大！")
    
    # 检查RSI
    rsi_conditions = conditions.get('rsi_extreme', {})
    if rsi > rsi_conditions.get('above', 70):
        alerts.append(f"{symbol} RSI超买: {rsi:.1f}")
    elif rsi < rsi_conditions.get('below', 30):
        alerts.append(f"{symbol} RSI超卖: {rsi:.1f}")
    
    return alerts
```

## 注意事项

1. **API限制**：Yahoo Finance 有请求频率限制
2. **延迟**：免费数据有15分钟延迟（美股）
3. **错误处理**：网络问题时要重试
4. **时差**：注意美股交易时间（北京时间21:30-次日4:00）

## 扩展功能

- 集成技术分析指标
- 支持A股（使用Tushare）
- 邮件/短信通知
- 自动交易执行
