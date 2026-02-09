# 纳斯达克100（NDX）RSI量化交易技术方案
## 一、方案目标
构建适配纳斯达克100指数（NDX/QQQ/TQQQ）特性的**RSI量化分析与交易信号系统**，整合「50日均线+成交量」验证逻辑，实现：

1. 自动化计算多周期RSI值，动态适配市场环境（牛市/熊市/震荡市）调整阈值；
2. 精准识别超买超卖、背离、金叉死叉等核心信号，过滤80%以上假信号；
3. 输出分交易风格的买卖信号，配套仓位管理、止损止盈等风控规则；
4. 支持历史回测、实时监控、信号告警全流程闭环。

## 二、系统整体架构
采用分层解耦架构，覆盖从数据获取到策略执行的全链路，各层职责清晰且可独立扩展：

```plain
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  数据层     │──│  计算层     │──│  信号层     │──│  策略层     │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
        │               │               │               │
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  回测层     │  │  风控层     │  │  部署监控层 │  │  可视化层   │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
```

## 三、核心模块详细设计
### 3.1 数据层：多维度数据采集与预处理
#### 3.1.1 数据源选型（优先级从高到低）
| 数据类型 | 数据源 | 数据频率 | 适用场景 |
| --- | --- | --- | --- |
| NDX/QQQ/TQQQ行情 | Yahoo Finance（免费）/Bloomberg（付费） | 1分钟/5分钟/日线/周线/月线 | 核心行情计算 |
| 成交量数据 | 同行情数据源 | 与行情频率一致 | 量能验证 |
| 50日均线数据 | 基于行情数据实时计算 | 与行情频率一致 | 趋势判断 |
| 权重股行情 | Yahoo Finance | 日线 | 背离信号验证（苹果/微软等） |
| VIX恐慌指数 | CBOE官网/TradingView | 日线 | 超买超卖信号增强 |


#### 3.1.2 数据预处理规则
1. **缺失值处理**：
    - 分钟级数据：用前一周期数据填充（如5分钟K线缺失，取前5分钟收盘价/成交量）；
    - 日线/周线数据：若缺失超过2个周期，标记为异常并暂停信号输出。
2. **复权处理**：QQQ/TQQQ等ETF需做前复权，避免除权导致价格失真。
3. **量能标准化**：计算「当日成交量/近20日均量」比值，统一量能判断标准（≥1.2倍=放量，≤0.8倍=缩量）。
4. **数据切片**：按交易风格拆分数据（短线：日线/30分钟；中线：周线；长线：月线）。

### 3.2 计算层：RSI核心计算与动态阈值适配
#### 3.2.1 多周期RSI计算公式（Python伪代码）
```python
import pandas as pd
import numpy as np

def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    计算N周期RSI值，适配纳指行情特性
    :param prices: 收盘价序列（如NDX日线收盘价）
    :param period: RSI周期（9/14/24/30/50）
    :return: RSI序列
    """
    # 步骤1：计算价格变动
    delta = prices.diff(1)
    # 步骤2：区分上涨幅度（U）和下跌幅度（D）
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    # 步骤3：计算N周期平均涨幅/跌幅（简单移动平均，适配纳指实操）
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    # 步骤4：计算RS和RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    # 填充初始周期的NaN值
    rsi = rsi.fillna(50)  # 初始无数据时默认多空平衡
    return rsi

# 示例：计算纳指14日RSI
# ndx_prices = pd.Series(NDX日线收盘价数据)
# ndx_rsi_14 = calculate_rsi(ndx_prices, period=14)
```

#### 3.2.2 市场环境识别与RSI阈值动态调整
通过「50日均线趋势+价格波动特征」识别市场环境，自动调整RSI阈值：

```python
def judge_market_env(prices: pd.Series, ma50: pd.Series) -> str:
    """
    识别纳指市场环境：牛市单边/熊市单边/震荡市
    :param prices: 收盘价序列
    :param ma50: 50日均线序列
    :return: 市场环境标签
    """
    # 50日均线趋势判断（连续20日斜率）
    ma50_slope = np.polyfit(range(len(ma50[-20:])), ma50[-20:], 1)[0]
    # 价格波动范围（近30日价格在50日均线±3%内为震荡）
    price_ma_diff = (prices - ma50) / ma50
    volatility_range = (price_ma_diff[-30:].max() - price_ma_diff[-30:].min())
    
    if ma50_slope > 0.001 and prices.iloc[-1] > ma50.iloc[-1]:
        return "bull"  # 牛市单边
    elif ma50_slope < -0.001 and prices.iloc[-1] < ma50.iloc[-1]:
        return "bear"  # 熊市单边
    elif volatility_range < 0.03:
        return "oscillate"  # 震荡市
    else:
        return "transition"  # 趋势过渡期（沿用前一周期环境）

def get_ndx_rsi_threshold(market_env: str) -> dict:
    """
    获取纳指不同市场环境下的RSI阈值
    :param market_env: 市场环境标签
    :return: 阈值字典
    """
    thresholds = {
        "bull": {"overbuy": 80, "strong_overbuy": 85, "oversell": 40, "strong_oversell": 35},
        "bear": {"overbuy": 60, "strong_overbuy": 65, "oversell": 20, "strong_oversell": 15},
        "oscillate": {"overbuy": 70, "strong_overbuy": 75, "oversell": 30, "strong_oversell": 25},
        "transition": {"overbuy": 70, "strong_overbuy": 75, "oversell": 30, "strong_oversell": 25}  # 默认震荡市
    }
    return thresholds[market_env]
```

### 3.3 信号层：多维度信号验证（RSI+50日均线+成交量）
#### 3.3.1 核心信号识别规则（以超买超卖为例）
```python
def generate_rsi_signal(
    prices: pd.Series,
    rsi: pd.Series,
    ma50: pd.Series,
    volume: pd.Series,
    market_env: str
) -> str:
    """
    生成纳指RSI交易信号：买入/卖出/观望/轻仓试多/轻仓试空
    :param prices: 收盘价序列
    :param rsi: 目标周期RSI序列
    :param ma50: 50日均线序列
    :param volume: 成交量序列
    :param market_env: 市场环境标签
    :return: 信号标签
    """
    # 获取当前市场环境的RSI阈值
    threshold = get_ndx_rsi_threshold(market_env)
    # 量能标准化（近20日均量）
    vol_20_avg = volume.rolling(window=20).mean().iloc[-1]
    current_vol_ratio = volume.iloc[-1] / vol_20_avg
    
    # 超卖信号判断（买入/轻仓试多）
    if rsi.iloc[-1] <= threshold["oversell"]:
        if market_env == "bear" and current_vol_ratio <= 0.8:  # 熊市超卖+缩量企稳
            return "buy_light"  # 轻仓试多
        elif market_env != "bear" and current_vol_ratio <= 0.8:  # 非熊市超卖+缩量
            return "buy"  # 买入
    # 超买信号判断（卖出/轻仓试空）
    elif rsi.iloc[-1] >= threshold["overbuy"]:
        if market_env == "bull" and current_vol_ratio <= 0.8:  # 牛市超买+缩量滞涨
            return "sell_light"  # 轻仓试空
        elif market_env != "bull" and current_vol_ratio >= 1.2:  # 非牛市超买+放量
            return "sell"  # 卖出
    # 无明确信号
    return "hold"
```

#### 3.3.2 背离信号识别（周线级优先）
```python
def detect_rsi_divergence(prices: pd.Series, rsi: pd.Series, period: str = "week") -> str:
    """
    识别纳指RSI背离：顶背离/底背离/无背离（周线级准确率最高）
    :param prices: 收盘价序列（日线/周线）
    :param rsi: RSI序列（对应周期）
    :param period: 周期标签（week/day）
    :return: 背离标签
    """
    # 取近2个高低点（周线取近8周，日线取近30日）
    lookback = 8 if period == "week" else 30
    recent_prices = prices[-lookback:]
    recent_rsi = rsi[-lookback:]
    
    # 价格新高/新低判断
    price_high1 = recent_prices.iloc[-1]
    price_high2 = recent_prices.iloc[-lookback//2]
    price_low1 = recent_prices.iloc[-1]
    price_low2 = recent_prices.iloc[-lookback//2]
    
    rsi_high1 = recent_rsi.iloc[-1]
    rsi_high2 = recent_rsi.iloc[-lookback//2]
    rsi_low1 = recent_rsi.iloc[-1]
    rsi_low2 = recent_rsi.iloc[-lookback//2]
    
    # 顶背离：价格新高，RSI未新高
    if price_high1 > price_high2 and rsi_high1 < rsi_high2:
        return "top_divergence"
    # 底背离：价格新低，RSI未新低
    elif price_low1 < price_low2 and rsi_low1 > rsi_low2:
        return "bottom_divergence"
    else:
        return "no_divergence"
```

### 3.4 策略层：分交易风格的执行逻辑
#### 3.4.1 策略参数配置（对应纳指实操手册）
| 交易风格 | RSI周期组合 | 核心周期 | 信号优先级 | 仓位上限 |
| --- | --- | --- | --- | --- |
| 短线（3-10天） | 9日（短）+24日（长） | 日线 | 金叉死叉>超买超卖>背离 | 80% |
| 中线（1-3月） | 14日（短）+30日（长） | 周线 | 背离>超买超卖>金叉死叉 | 70% |
| 长线（6月+） | 24日（短）+50日（长） | 月线 | 趋势确认>背离>超买超卖 | 80% |


#### 3.4.2 短线策略执行逻辑（伪代码）
```python
def short_term_strategy(ndx_data: pd.DataFrame) -> dict:
    """
    纳指短线（3-10天）策略执行逻辑
    :param ndx_data: 包含close/rsi9/rsi24/ma50/volume的DataFrame
    :return: 策略决策（信号+仓位+止损止盈）
    """
    # 1. 市场环境识别
    market_env = judge_market_env(ndx_data["close"], ndx_data["ma50"])
    # 2. 金叉/死叉判断
    rsi9 = ndx_data["rsi9"].iloc[-1]
    rsi24 = ndx_data["rsi24"].iloc[-1]
    rsi9_prev = ndx_data["rsi9"].iloc[-2]
    rsi24_prev = ndx_data["rsi24"].iloc[-2]
    golden_cross = (rsi9 > rsi24) and (rsi9_prev < rsi24_prev)  # 金叉
    death_cross = (rsi9 < rsi24) and (rsi9_prev > rsi24_prev)    # 死叉
    
    # 3. 信号验证（金叉+成交量+均线）
    vol_ratio = ndx_data["volume"].iloc[-1] / ndx_data["volume"].rolling(20).mean().iloc[-1]
    price_above_ma50 = ndx_data["close"].iloc[-1] > ndx_data["ma50"].iloc[-1]
    
    # 4. 决策输出
    decision = {"signal": "hold", "position": 0, "stop_loss": 0, "take_profit": 0}
    if golden_cross and (30 <= rsi9 <= 50) and vol_ratio >= 1.2 and price_above_ma50:
        decision["signal"] = "buy"
        decision["position"] = 0.4  # 加仓40%
        decision["stop_loss"] = ndx_data["close"].iloc[-1] * 0.97  # 止损3%
        decision["take_profit"] = ndx_data["close"].iloc[-1] * 1.07  # 止盈7%（RSI达70）
    elif death_cross and (50 <= rsi9 <= 70) and vol_ratio >= 1.2 and not price_above_ma50:
        decision["signal"] = "sell"
        decision["position"] = -0.4  # 减仓40%
        decision["stop_loss"] = ndx_data["close"].iloc[-1] * 1.03  # 止损3%
        decision["take_profit"] = ndx_data["close"].iloc[-1] * 0.93  # 止盈7%（RSI达30）
    return decision
```

### 3.5 回测层：历史数据验证与参数优化
#### 3.5.1 回测框架选型与核心指标
+ **框架**：使用Backtrader/PyAlgoTrade（Python），适配纳指1分钟/日线/周线数据；
+ **回测周期**：2018-2025年（覆盖牛市/熊市/震荡市完整周期）；
+ **核心评估指标**：

| 指标 | 目标值（纳指策略） |
| --- | --- |
| 胜率 | ≥60%（短线）/≥68%（中线） |
| 盈亏比 | ≥1.5 |
| 最大回撤 | ≤20% |
| 夏普比率 | ≥1.2 |


#### 3.5.2 参数优化方法
采用「网格搜索+交叉验证」优化RSI周期和阈值：

1. 网格范围：RSI短周期（6-14）、长周期（24-50）、超买阈值（60-85）、超卖阈值（15-40）；
2. 交叉验证：将历史数据分为5个区间，避免过拟合；
3. 优化目标：最大化夏普比率，同时控制最大回撤≤20%。

### 3.6 风控层：纳指专属风险控制
#### 3.6.1 仓位管理规则
| 市场环境 | 最大仓位 | RSI超买/超卖调整 | 背离信号调整 |
| --- | --- | --- | --- |
| 牛市 | 80% | RSI>80→降至50% | 底背离→加仓至70% |
| 熊市 | 30% | RSI<20→升至50% | 顶背离→减仓至10% |
| 震荡市 | 50% | RSI=65→减20%/RSI=35→加20% | - |


#### 3.6.2 止损止盈精细化规则
| 操作类型 | 止损比例 | 止盈比例 | 特殊调整（纳指高波动） |
| --- | --- | --- | --- |
| 超买/超卖操作 | 2-3% | 5-8% | 极端行情（VIX>30）→止损扩大至5% |
| 背离操作 | 3-5% | 10-15% | 周线背离→止盈扩大至20% |
| 金叉/死叉操作 | 3% | 7% | 成交量不足→止损缩小至2% |


### 3.7 部署与监控层
#### 3.7.1 部署架构
+ **开发环境**：Python 3.9+，依赖pandas/numpy/Backtrader/TA-Lib；
+ **部署方式**：Docker容器化部署（便于环境隔离）；
+ **定时任务**：
    - 分钟级数据：每5分钟更新一次（短线策略）；
    - 日线/周线数据：每日收盘后更新（中线/长线策略）；
    - 信号生成：数据更新后1分钟内完成。

#### 3.7.2 监控与告警
| 监控维度 | 告警触发条件 | 告警方式 |
| --- | --- | --- |
| 数据异常 | 数据缺失>2个周期/量能异常 | 钉钉/邮件 |
| 信号异常 | 连续3次假信号（止损触发） | 短信+钉钉 |
| 行情极端波动 | 纳指单日涨跌幅>5%/VIX>40 | 实时语音告警 |
| 策略绩效 | 最大回撤>20%/胜率<50% | 邮件+后台通知 |


## 四、系统验收标准
1. **计算准确性**：RSI值与TradingView纳指RSI偏差≤0.5；
2. **信号有效性**：回测胜率≥60%（短线）/≥68%（中线），盈亏比≥1.5；
3. **实时性**：分钟级信号生成延迟≤1分钟，日线信号延迟≤5分钟；
4. **稳定性**：连续运行30天无崩溃，数据异常处理率100%；
5. **风控有效性**：实盘模拟最大回撤≤20%，止损触发准确率≥95%。

## 五、扩展方向
1. 集成机器学习模型（如LSTM）预测RSI趋势，进一步提升信号准确率；
2. 对接券商API，实现策略自动执行（需合规授权）；
3. 支持多标的扩展（如纳指权重股、纳斯达克ETF等）；
4. 增加多语言可视化面板（Web端），支持实时查看信号和绩效。









