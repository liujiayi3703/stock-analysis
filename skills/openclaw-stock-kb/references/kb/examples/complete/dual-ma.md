# 双均线策略完整实现

## 策略概述

双均线策略是最经典的趋势跟踪策略之一，利用短期和长期移动平均线的交叉产生交易信号。

## 策略逻辑

### 买入信号（金叉）
短期均线上穿长期均线

### 卖出信号（死叉）
短期均线下穿长期均线

## 完整代码

```python
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

class DualMAStrategy:
    """
    双均线策略
    """
    def __init__(self, short_window=5, long_window=20):
        self.short_window = short_window
        self.long_window = long_window
        self.name = f"Dual_MA_{short_window}_{long_window}"
    
    def generate_signals(self, df):
        """
        生成交易信号
        """
        df = df.copy()
        
        # 计算均线
        df['short_ma'] = df['close'].rolling(window=self.short_window).mean()
        df['long_ma'] = df['close'].rolling(window=self.long_window).mean()
        
        # 生成信号：1买入，-1卖出，0持有
        df['signal'] = 0
        df['signal'][self.short_window:] = np.where(
            df['short_ma'][self.short_window:] > df['long_ma'][self.short_window:], 
            1, 0
        )
        
        # 产生交易信号（信号变化时）
        df['positions'] = df['signal'].diff()
        
        return df
    
    def backtest(self, df, initial_capital=100000):
        """
        简单回测
        """
        df = self.generate_signals(df)
        
        # 计算持仓
        df['holdings'] = df['signal'] * df['close']
        
        # 计算收益
        df['returns'] = df['close'].pct_change()
        df['strategy_returns'] = df['signal'].shift(1) * df['returns']
        
        # 计算累计收益
        df['cumulative_market'] = (1 + df['returns']).cumprod()
        df['cumulative_strategy'] = (1 + df['strategy_returns']).cumprod()
        
        # 计算资金曲线
        df['portfolio'] = initial_capital * df['cumulative_strategy']
        
        return df
    
    def plot_results(self, df):
        """
        绘制结果
        """
        fig, axes = plt.subplots(3, 1, figsize=(12, 10))
        
        # 价格和均线
        ax1 = axes[0]
        ax1.plot(df.index, df['close'], label='Price', alpha=0.7)
        ax1.plot(df.index, df['short_ma'], label=f'MA{self.short_window}')
        ax1.plot(df.index, df['long_ma'], label=f'MA{self.long_window}')
        
        # 标记买卖点
        buys = df[df['positions'] == 1].index
        sells = df[df['positions'] == -1].index
        ax1.scatter(buys, df.loc[buys, 'close'], marker='^', color='g', s=100, label='Buy')
        ax1.scatter(sells, df.loc[sells, 'close'], marker='v', color='r', s=100, label='Sell')
        
        ax1.set_title('Dual Moving Average Strategy')
        ax1.legend()
        ax1.grid(True)
        
        # 持仓
        ax2 = axes[1]
        ax2.plot(df.index, df['signal'], label='Position')
        ax2.set_title('Position (1=Long, 0=Out)')
        ax2.legend()
        ax2.grid(True)
        
        # 累计收益
        ax3 = axes[2]
        ax3.plot(df.index, df['cumulative_market'], label='Market', alpha=0.7)
        ax3.plot(df.index, df['cumulative_strategy'], label='Strategy')
        ax3.set_title('Cumulative Returns')
        ax3.legend()
        ax3.grid(True)
        
        plt.tight_layout()
        plt.savefig('dual_ma_backtest.png', dpi=150)
        plt.show()

# 使用示例
if __name__ == "__main__":
    # 加载数据
    df = pd.read_csv('AAPL.csv', index_col='date', parse_dates=True)
    
    # 创建策略
    strategy = DualMAStrategy(short_window=5, long_window=20)
    
    # 运行回测
    results = strategy.backtest(df, initial_capital=100000)
    
    # 计算绩效指标
    total_return = results['cumulative_strategy'].iloc[-1] - 1
    print(f"总收益率: {total_return*100:.2f}%")
    
    # 绘制结果
    strategy.plot_results(results)
```

## 参数优化

```python
from itertools import product

def optimize_parameters(df, short_range=range(5, 20), long_range=range(20, 60)):
    """
    参数优化
    """
    best_return = -np.inf
    best_params = None
    
    for short, long in product(short_range, long_range):
        if short >= long:
            continue
            
        strategy = DualMAStrategy(short_window=short, long_window=long)
        results = strategy.backtest(df)
        
        total_return = results['cumulative_strategy'].iloc[-1] - 1
        
        if total_return > best_return:
            best_return = total_return
            best_params = (short, long)
    
    print(f"最优参数: 短周期={best_params[0]}, 长周期={best_params[1]}")
    print(f"最优收益: {best_return*100:.2f}%")
    
    return best_params
```

## 绩效评估

```python
def calculate_metrics(returns):
    """
    计算绩效指标
    """
    metrics = {
        '总收益率': returns.cumsum().iloc[-1],
        '年化收益率': returns.mean() * 252,
        '年化波动率': returns.std() * np.sqrt(252),
        '夏普比率': returns.mean() / returns.std() * np.sqrt(252),
        '最大回撤': (returns.cumsum() - returns.cumsum().cummax()).min(),
        '胜率': (returns > 0).mean()
    }
    return metrics
```

## 注意事项

1. **过拟合风险**: 参数优化可能导致过拟合
2. **滑点成本**: 实际交易中需要考虑手续费和滑点
3. **市场环境**: 趋势市效果好，震荡市效果差
4. **资金管理**: 每笔交易固定风险比例

## 改进方向

- 添加过滤器（如 ADX>20 才交易）
- 加入止损机制
- 考虑交易成本
- 多品种组合

## 相关策略

- [简单均值回归](../../strategies/mean-reversion/simple-mean-reversion.md)
- [趋势跟踪](../../strategies/momentum/trend-following.md)
- [MACD 策略](../macd-strategy.md)
