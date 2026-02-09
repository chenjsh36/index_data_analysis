# 技术方案设计（Technical Design）— v3 BRD 对齐修正版

**文档版本**：3.0  
**产出日期**：2026-02-09  
**依据**：研发流程步骤 4 - 技术方案设计  
**上游输入**：`v3/02-requirements-documentation.md`（FIX-01 ~ FIX-13）、`context/tech_v2.md`  
**设计原则**：最小改动原则 — 保持现有分层架构、接口签名与返回格式不变，仅在信号层、风控层和配置层做修正与增强

---

## 一、修改范围总览

```
ndx_rsi/
├── indicators/
│   ├── ma.py               [修改] 新增 MA5、MA20 便捷函数
│   ├── market_env.py        [修改] 震荡市阈值修正；阈值加载支持配置覆盖
│   └── __init__.py          [修改] 导出新函数
├── signal/
│   ├── rsi_signals.py       [修改] 超买超卖强度分级；金叉/死叉确认增强
│   ├── trend_volume.py      [不变]
│   └── combine.py           [重写] 核心组合逻辑全面重构
├── risk/
│   └── control.py           [修改] 信号级止损止盈；动态仓位上限
├── strategy/
│   └── ndx_short.py         [修改] 传入 MA5/MA20；适配新接口
├── backtest/
│   └── runner.py            [修改] 预计算 MA5/MA20；适配信号级风控
config/
└── strategy.yaml            [修改] 阈值修正；新增配置项
```

---

## 二、数据流图（v3 修正后）

```
                         ┌──────────────┐
                         │  strategy.yaml│ ← 配置层
                         └──────┬───────┘
                                │
  历史数据 ──→ 预计算指标 ──→ 策略入口 ──→ 信号输出 ──→ 风控 ──→ 回测/执行
                │                │              │            │
         ┌──────┴──────┐   ┌────┴────┐   ┌────┴────┐  ┌────┴────┐
         │ RSI(9/24)   │   │market_env│   │combine  │  │control  │
         │ MA50        │   │judge     │   │_v3()    │  │_v3()    │
         │ MA5  [新增] │   └─────────┘   └─────────┘  └─────────┘
         │ MA20 [新增] │                      │
         │ volume_ratio│               ┌──────┴──────┐
         └─────────────┘               │  rsi_signals│
                                       │  _v3()      │
                                       └─────────────┘
```

---

## 三、各模块详细设计

### 3.1 配置层修改：`config/strategy.yaml`

**变更点**：震荡市阈值修正 + 新增 `signal_risk` 和 `dynamic_cap`。

```yaml
strategies:
  NDX_short_term:
    index_code: "QQQ"
    period_type: "short"
    hold_days: [3, 10]
    use_divergence: false

    rsi_params:
      short_period: 9
      long_period: 24
      thresholds:
        bull:
          overbuy: 80
          strong_overbuy: 85
          oversell: 40
          strong_oversell: 35
        bear:
          overbuy: 60
          strong_overbuy: 65
          oversell: 20
          strong_oversell: 15
        oscillate:                # [FIX-02] 修正
          overbuy: 65             # 原 70 → 65
          strong_overbuy: 70      # 原 75 → 70
          oversell: 35            # 原 30 → 35
          strong_oversell: 30     # 原 25 → 30
        transition:
          overbuy: 70
          strong_overbuy: 75
          oversell: 30
          strong_oversell: 25

    risk_control:
      max_position: 0.8
      stop_loss_ratio: 0.03       # 默认兜底值
      take_profit_ratio: 0.07
      is_leverage_etf: false

      # [FIX-09] 新增：信号级止损止盈
      signal_risk:
        overbought:    { stop_loss_ratio: 0.02, take_profit_ratio: 0.05 }
        oversell:      { stop_loss_ratio: 0.02, take_profit_ratio: 0.05 }
        golden_cross:  { stop_loss_ratio: 0.03, take_profit_ratio: 0.07 }
        death_cross:   { stop_loss_ratio: 0.03, take_profit_ratio: 0.07 }
        bullish_divergence: { stop_loss_ratio: 0.04, take_profit_ratio: 0.08 }
        bearish_divergence: { stop_loss_ratio: 0.04, take_profit_ratio: 0.08 }
        trend_pullback:     { stop_loss_ratio: 0.03, take_profit_ratio: 0.06 }
        trend_bounce_sell:  { stop_loss_ratio: 0.03, take_profit_ratio: 0.06 }

      # [FIX-12] 新增：动态仓位上限
      dynamic_cap:
        bull:      { default: 0.8, rsi_above_strong_ob: 0.5 }
        bear:      { default: 0.3, rsi_below_strong_os: 0.5 }
        oscillate: { default: 0.5 }
        transition: { default: 0.5 }
```

**向后兼容**：新增项均通过 `.get()` + 默认值访问，缺失时回退到 v2 行为。

---

### 3.2 指标层修改：`indicators/ma.py`

**变更**：新增 `calculate_ma5()` 和 `calculate_ma20()` 便捷函数。

```python
# indicators/ma.py  —— 新增部分

def calculate_ma5(series: pd.Series) -> pd.Series:
    """MA5：5日简单移动平均，用于金叉/死叉价格确认。 [FIX-07]"""
    return series.rolling(window=5, min_periods=1).mean()

def calculate_ma20(series: pd.Series) -> pd.Series:
    """MA20：20日简单移动平均，用于下降趋势反转确认。 [FIX-13]"""
    return series.rolling(window=20, min_periods=1).mean()
```

**`indicators/__init__.py`** 新增导出 `calculate_ma5`, `calculate_ma20`。

---

### 3.3 指标层修改：`indicators/market_env.py`

**变更**：震荡市阈值修正为 65/35。

```python
# 修改 _THRESHOLDS 中的 oscillate 条目  [FIX-02]
_THRESHOLDS = {
    "bull":       {"overbuy": 80, "strong_overbuy": 85, "oversell": 40, "strong_oversell": 35},
    "bear":       {"overbuy": 60, "strong_overbuy": 65, "oversell": 20, "strong_oversell": 15},
    "oscillate":  {"overbuy": 65, "strong_overbuy": 70, "oversell": 35, "strong_oversell": 30},
    "transition": {"overbuy": 70, "strong_overbuy": 75, "oversell": 30, "strong_oversell": 25},
}
```

新增函数：支持从配置加载阈值覆盖（优先配置 > 硬编码）。

```python
def get_rsi_thresholds(market_env: str, config_thresholds: dict = None) -> dict:
    """返回阈值。若传入 config_thresholds 则优先使用（配置覆盖）。"""
    base = _THRESHOLDS.get(market_env, _THRESHOLDS["transition"]).copy()
    if config_thresholds and market_env in config_thresholds:
        base.update(config_thresholds[market_env])
    return base
```

---

### 3.4 信号层修改：`signal/rsi_signals.py`

#### 3.4.1 超买超卖强度分级 [FIX-08]

```python
def check_overbought_oversold(
    rsi_short: float,
    rsi_long: float,
    market_env: str,
    config_thresholds: dict = None,
) -> tuple:
    """
    返回 (ob_result, os_result)。
    ob_result: None | "overbought" | "strong_overbought"
    os_result: None | "oversell" | "strong_oversell"
    """
    th = get_rsi_thresholds(market_env, config_thresholds)
    strong_ob = th.get("strong_overbuy", 999)
    ob = th.get("overbuy", 70)
    strong_os = th.get("strong_oversell", -999)
    os_val = th.get("oversell", 30)

    ob_result = None
    os_result = None
    if rsi_short >= strong_ob:
        ob_result = "strong_overbought"
    elif rsi_short >= ob:
        ob_result = "overbought"
    if rsi_short <= strong_os:
        os_result = "strong_oversell"
    elif rsi_short <= os_val:
        os_result = "oversell"
    return ob_result, os_result
```

**接口变更**：返回值类型不变（tuple），但字符串新增 `"strong_overbought"` / `"strong_oversell"` 两个可能值。下游需处理新值或将 `"strong_*"` 视同普通超买超卖。

#### 3.4.2 金叉/死叉确认增强 [FIX-07]

```python
def check_golden_death_cross(
    rsi_short_cur: float,
    rsi_long_cur: float,
    rsi_short_prev: float,
    rsi_long_prev: float,
    market_env: str,
    close: float = None,       # [新增] 当前收盘价
    ma5: float = None,         # [新增] 5日均线值
) -> str | None:
    """
    金叉/死叉判定 + BRD 确认条件：
    - 无效区间过滤：金叉 mid>70 → None，死叉 mid<30 → None  [FIX-07]
    - 金叉需 close > ma5（可选）
    - 死叉需 close < ma5（可选）
    """
    golden = rsi_short_prev < rsi_long_prev and rsi_short_cur > rsi_long_cur
    death = rsi_short_prev > rsi_long_prev and rsi_short_cur < rsi_long_cur
    mid = (rsi_short_cur + rsi_long_cur) / 2

    # 无效信号过滤 [FIX-07]
    if golden and mid > 70:
        return None
    if death and mid < 30:
        return None

    if golden and 30 <= mid <= 60:
        # MA5 确认（可选）
        if close is not None and ma5 is not None and close < ma5:
            return None  # 价格未站上 MA5，金叉无效
        # 双 RSI 站上 50 确认
        if rsi_short_cur > 50 and rsi_long_cur > 50:
            return "golden_cross"
        # 即使双 RSI 未同时过 50，在 30-50 区间仍视为有效（区间本身含义）
        return "golden_cross"

    if death and 40 <= mid <= 70:
        if close is not None and ma5 is not None and close > ma5:
            return None  # 价格未跌破 MA5，死叉无效
        return "death_cross"

    return None
```

**设计说明**：`close` 和 `ma5` 为可选参数，不传时退化为 v2 行为，保证向后兼容。BRD 中"双 RSI 站上 50"在 30-50 区间金叉语境下是后续确认条件，此处作为增强判断而非硬性拒绝，避免过度过滤。

---

### 3.5 信号层重写：`signal/combine.py`（核心）

这是修改量最大的文件，需全面重构以对齐 BRD 第三章全部规则。

#### 3.5.1 新函数签名

```python
def generate_signal_dict(
    df: pd.DataFrame,
    market_env: str,
    rsi_short_col: str = "rsi_9",
    rsi_long_col: str = "rsi_24",
    ma50_col: str = "ma50",
    ma5_col: str = "ma5",             # [新增] FIX-07
    ma20_col: str = "ma20",           # [新增] FIX-13
    volume_ratio_col: str = "volume_ratio",
    use_divergence: bool = False,
    divergence_lookback: int = 20,
    config_thresholds: dict = None,   # [新增] 配置阈值覆盖
) -> Dict[str, Any]:
```

返回值格式不变：`{"signal", "position", "reason", "ts"}`，新增可选字段 `"strength"` 标记强度。

#### 3.5.2 完整逻辑伪代码（按 BRD 场景 1/2/3 组织）

```
输入: df, market_env, 各列名, 配置参数
提取: row(当前K线), prev(前一K线), rsi_s, rsi_l, vol_ratio, close, ma5, ma20

1. 计算基础信号:
   trend = get_trend(prices, ma50)
   vol_type = get_volume_type(vol_ratio)
   ob, os = check_overbought_oversold(rsi_s, rsi_l, market_env)   # 含强度分级 [FIX-08]
   cross = check_golden_death_cross(rsi_s, rsi_l, prev_rsi_s, prev_rsi_l, market_env, close, ma5)
   divergence = check_divergence(...)  # 仅 use_divergence=True 时

2. 背离信号（按趋势分发） [FIX-10]:
   IF use_divergence AND divergence:
     IF trend == UP:
       - bullish_divergence + vol_ratio >= 1.2 → buy 0.5     # BRD 场景1
       - bearish_divergence → hold（上升趋势忽略顶背离）
     ELIF trend == DOWN:
       - bearish_divergence + vol_type == "down" → sell -1.0  # BRD 场景2（清仓）
       - bullish_divergence → hold（下降趋势忽略底背离）
     ELSE (SIDE):
       - bullish_divergence + vol_type == "down" → buy 0.3
       - bearish_divergence + vol_ratio >= 1.2 → sell -0.3

3. 金叉/死叉（按趋势+量能确认） [FIX-03, FIX-07]:
   IF trend == UP or trend == DOWN:
     - golden_cross + vol_ratio >= 1.3 → buy 0.4          # BRD: ≥30% 增幅
     - death_cross + vol_ratio >= 1.3 → sell -0.4
   ELIF trend == SIDE:                                      # [FIX-03] 震荡市
     - golden_cross + mid 30-50 + vol_type == "down" → buy 0.3   # 金叉需缩量
     - death_cross + mid 50-70 + vol_ratio >= 1.2 → sell -0.3    # 死叉需放量
     - golden_cross + mid > 50 + vol_ratio >= 1.2 → hold（假信号）
     - death_cross + mid < 30 + vol_type == "down" → hold（假信号）

4. 趋势内超买超卖 + 量能过滤:

   4a. 上升趋势 [FIX-04, FIX-05]:
     # BRD 场景1 第1行：RSI 回踩 + 缩量 → 买
     - (os OR 40 <= rsi_s <= 50) AND vol_type == "down":
         → buy 0.3, reason="oversell" 或 "trend_pullback"
     # BRD 场景1 第2行：RSI 回踩 + 放量 → 不买 [FIX-04]
     - (os OR 40 <= rsi_s <= 50) AND vol_ratio >= 1.2:
         → hold, reason="pullback_volume_reject"
     # BRD 场景1 第3行：超买 + 缩量滞涨 → 轻减
     - ob AND vol_type == "down":
         → sell_light -0.2 (普通超买) 或 -0.3 (强超买) [FIX-08]
     # BRD 场景1 第4行：超买 + 放量 → 继续持仓 [FIX-05]
     - ob AND vol_ratio >= 1.2:
         → hold, reason="overbought_with_volume_ignore"

   4b. 下降趋势 [FIX-06]:
     # BRD 场景2 第1行：RSI反弹50-60 + 放量 → 减仓
     - (ob OR 50 <= rsi_s <= 60) AND vol_ratio >= 1.2:
         → sell -0.4 (放量滞涨)
     # BRD 场景2 第2行：RSI反弹50-60 + 缩量 → 轻减 [FIX-06]
     - 50 <= rsi_s <= 60 AND vol_type == "down":
         → sell_light -0.2, reason="trend_bounce_sell_light"
     # BRD 场景2 第3行：超卖 + 放量下跌 → 不抄底
     - os AND vol_ratio >= 1.2:
         → hold, reason="oversell_volume_reject"
     # BRD 场景2 第4行：超卖 + 缩量企稳 → 轻仓试多
     - os AND vol_type == "down":
         → buy_light 0.3

   4c. 震荡趋势 [FIX-01]:
     # BRD 场景3 第1行：超买 + 放量 → 减仓
     - ob AND vol_ratio >= 1.2:
         → sell -0.3 (普通) 或 -0.4 (强超买) [FIX-08]
     # BRD 场景3 第2行：超卖 + 缩量 → 加仓
     - os AND vol_type == "down":
         → buy 0.3 (普通) 或 0.4 (强超卖) [FIX-08]
     # 超买但缩量 / 超卖但放量 → hold（量能不匹配）

5. 默认: hold, position=0.0, reason="no_signal"
```

#### 3.5.3 优先级规则

```
背离 > 金叉/死叉 > 超买超卖+量能过滤 > hold
```

在同一优先级内，按 BRD 规则表从上到下匹配，首个命中即返回。

#### 3.5.4 强度分级仓位映射 [FIX-08]

| 信号 | 普通 | 强 |
|------|------|-----|
| 上升趋势超买+缩量 | sell_light -0.2 | sell_light -0.3 |
| 下降趋势超买+放量 | sell -0.3 | sell -0.4 |
| 震荡超买+放量 | sell -0.3 | sell -0.4 |
| 震荡超卖+缩量 | buy 0.3 | buy 0.4 |

---

### 3.6 风控层修改：`risk/control.py`

#### 3.6.1 信号级止损止盈 [FIX-09]

```python
def get_stop_loss_take_profit(
    close: float,
    signal: str,
    reason: str = "",                 # [新增] 信号原因
    is_leverage_etf: bool = False,
    stop_ratio: float = None,
    take_ratio: float = None,
    signal_risk_config: dict = None,  # [新增] signal_risk 配置
) -> Dict[str, float]:
    """
    优先级：signal_risk_config[reason] > 传入 stop_ratio/take_ratio > 默认值
    """
    # 1. 从 signal_risk 配置中按 reason 查找
    if signal_risk_config and reason in signal_risk_config:
        sr = signal_risk_config[reason]
        stop_ratio = stop_ratio or sr.get("stop_loss_ratio")
        take_ratio = take_ratio or sr.get("take_profit_ratio")
    # 2. 兜底默认
    if stop_ratio is None:
        stop_ratio = 0.05 if is_leverage_etf else 0.03
    if take_ratio is None:
        take_ratio = 0.07
    # 3. 计算止损止盈价（逻辑不变）
    ...
```

#### 3.6.2 动态仓位上限 [FIX-12]

```python
def apply_position_cap(
    position: float,
    market_env: str,
    rsi_short: float = None,          # [新增]
    dynamic_cap_config: dict = None,  # [新增]
) -> float:
    """
    基础 cap + RSI 水平动态调整：
    - 牛市 RSI > strong_overbuy → cap 降至 0.5
    - 熊市 RSI < strong_oversell → cap 升至 0.5
    """
    base_caps = {"bull": 0.8, "bear": 0.3, "oscillate": 0.5, "transition": 0.5}
    cap = base_caps.get(market_env, 0.5)

    # 动态调整
    if dynamic_cap_config and market_env in dynamic_cap_config:
        dc = dynamic_cap_config[market_env]
        cap = dc.get("default", cap)
        if rsi_short is not None:
            if market_env == "bull" and "rsi_above_strong_ob" in dc:
                th = get_rsi_thresholds(market_env)
                if rsi_short > th.get("strong_overbuy", 999):
                    cap = dc["rsi_above_strong_ob"]
            elif market_env == "bear" and "rsi_below_strong_os" in dc:
                th = get_rsi_thresholds(market_env)
                if rsi_short < th.get("strong_oversell", -999):
                    cap = dc["rsi_below_strong_os"]

    if position > 0:
        return min(position, cap)
    return max(position, -cap)
```

---

### 3.7 策略层修改：`strategy/ndx_short.py`

**变更点**：预计算 MA5/MA20，传递配置到信号和风控函数。

```python
class NDXShortTermRSIStrategy(BaseTradingStrategy):

    def generate_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        # ... 现有数据校验和指标计算 ...

        # [新增] MA5、MA20
        if "ma5" not in data.columns:
            data = data.copy()
            data["ma5"] = calculate_ma(data["close"], 5)
        if "ma20" not in data.columns:
            data = data.copy()
            data["ma20"] = calculate_ma(data["close"], 20)

        # ... market_env、extreme_market 检查不变 ...

        # 传入配置阈值
        config_thresholds = self.config.get("rsi_params", {}).get("thresholds", None)

        sig = generate_signal_dict(
            data, market_env,
            ma5_col="ma5",               # [新增]
            ma20_col="ma20",             # [新增]
            use_divergence=use_divergence,
            divergence_lookback=divergence_lookback,
            config_thresholds=config_thresholds,  # [新增]
        )

        # 动态仓位 cap [FIX-12]
        dynamic_cap = self.config.get("risk_control", {}).get("dynamic_cap", None)
        pos = sig.get("position", 0.0)
        rsi_cur = data["rsi_9"].iloc[-1]
        sig["position"] = apply_position_cap(
            pos, market_env,
            rsi_short=rsi_cur,
            dynamic_cap_config=dynamic_cap,
        )
        return sig

    def calculate_risk(self, signal: Dict[str, Any], data: pd.DataFrame) -> Dict[str, Any]:
        # ... 现有校验 ...
        rc = self.config.get("risk_control", {})
        signal_risk_config = rc.get("signal_risk", None)  # [新增] FIX-09
        reason = signal.get("reason", "")
        return get_stop_loss_take_profit(
            close,
            signal.get("signal", "hold"),
            reason=reason,                         # [新增]
            is_leverage_etf=rc.get("is_leverage_etf", False),
            stop_ratio=rc.get("stop_loss_ratio"),
            take_ratio=rc.get("take_profit_ratio"),
            signal_risk_config=signal_risk_config,  # [新增]
        )
```

---

### 3.8 回测层修改：`backtest/runner.py`

**变更点**：预计算 MA5/MA20 列。

```python
# 在 run_backtest() 的指标预计算段新增：
df["ma5"] = calculate_ma(df["close"], 5)    # [新增]
df["ma20"] = calculate_ma(df["close"], 20)  # [新增]
```

其余回测逻辑不变。止损/止盈价已在 `entries` 中记录开仓时的 `risk` 返回值，信号级风控通过策略的 `calculate_risk()` 自动传递，回测引擎无需感知。

---

## 四、FIX-11 平仓信号设计（Medium）

**设计方案**：在 `generate_signal_dict()` 中增加可选参数 `current_position_info`，包含当前持仓方向和入场 reason。

```python
def generate_signal_dict(
    ...,
    current_position_info: dict = None,  # {"direction": "long"|"short", "entry_reason": "overbought"|...}
) -> Dict[str, Any]:
    """
    平仓信号 [FIX-11]：
    - 若持仓由超买信号进入（short） + RSI 回落至 65 以下 → 平仓
    - 若持仓由超卖信号进入（long） + RSI 回升至 35 以上 → 平仓
    """
    if current_position_info:
        direction = current_position_info.get("direction")
        entry_reason = current_position_info.get("entry_reason", "")
        if direction == "short" and "overbought" in entry_reason and rsi_s < 65:
            return {"signal": "close", "position": 0.0,
                    "reason": "close_overbought_revert", "ts": ...}
        if direction == "long" and "oversell" in entry_reason and rsi_s > 35:
            return {"signal": "close", "position": 0.0,
                    "reason": "close_oversell_revert", "ts": ...}
```

**回测适配**：`runner.py` 在调用 `strategy.generate_signal()` 时传入当前持仓信息。此为 Medium 优先级，可在第 3 批实施。

---

## 五、接口变更汇总

| 函数 | 变更类型 | 新增参数 | 兼容性 |
|------|----------|----------|--------|
| `check_overbought_oversold()` | 返回值扩展 | `config_thresholds` | 向后兼容（新值为字符串超集） |
| `check_golden_death_cross()` | 参数扩展 | `close`, `ma5` | 默认 None，不传时退化为 v2 |
| `generate_signal_dict()` | 参数扩展 | `ma5_col`, `ma20_col`, `config_thresholds`, `current_position_info` | 均有默认值 |
| `get_stop_loss_take_profit()` | 参数扩展 | `reason`, `signal_risk_config` | 默认空，不传时退化 |
| `apply_position_cap()` | 参数扩展 | `rsi_short`, `dynamic_cap_config` | 默认 None，不传时退化 |

所有变更均**向后兼容** — 不传新参数时行为与 v2 完全一致。

---

## 六、测试方案

### 6.1 单元测试（按 FIX 编号）

| FIX | 测试文件 | 测试用例 |
|-----|----------|----------|
| FIX-01 | `test_combine.py` | 震荡市：超买+缩量→hold, 超买+放量→sell, 超卖+放量→hold, 超卖+缩量→buy |
| FIX-02 | `test_market_env.py` | 震荡市阈值为 65/35 |
| FIX-03 | `test_combine.py` | 震荡市：金叉+缩量→buy, 金叉+放量→hold, 死叉+放量→sell, 死叉+缩量→hold |
| FIX-04 | `test_combine.py` | 上升趋势：RSI回踩+放量→hold, RSI回踩+缩量→buy |
| FIX-05 | `test_combine.py` | 上升趋势：超买+放量→hold, 超买+缩量→sell_light |
| FIX-06 | `test_combine.py` | 下降趋势：RSI50-60+缩量→sell_light, RSI50-60+放量→sell |
| FIX-07 | `test_rsi_signals.py` | 金叉 mid>70→None, 死叉 mid<30→None, 金叉+close<ma5→None |
| FIX-08 | `test_rsi_signals.py` | 牛市 RSI=82→strong_overbought, RSI=78→overbought |
| FIX-09 | `test_control.py` | reason="overbought"→SL=2%, reason="golden_cross"→SL=3% |
| FIX-10 | `test_combine.py` | 上升趋势+顶背离→hold, 下降趋势+底背离→hold |
| FIX-11 | `test_combine.py` | 持仓short+RSI<65→close, 持仓long+RSI>35→close |
| FIX-12 | `test_control.py` | 牛市 RSI>85→cap=0.5, 熊市 RSI<15→cap=0.5 |
| FIX-13 | `test_indicators.py` | MA20 值正确 |

### 6.2 回测对比

修正前后运行相同参数回测（QQQ, 2018-2025），对比：
- 信号数量变化（预期减少 — 更严格过滤）
- 胜率变化（预期提升 — 假信号减少）
- 最大回撤变化
- 夏普比率变化

---

## 七、实施顺序与依赖关系

```
第 1 批 (Critical, 无依赖):
  FIX-02 → 修改 strategy.yaml + market_env.py（1个文件改常量）
  FIX-01 → 修改 combine.py 震荡分支（依赖 FIX-02 先完成阈值修正）
  FIX-04 → 修改 combine.py 上升趋势分支
  FIX-05 → 修改 combine.py 上升趋势分支（与 FIX-04 同批）
  FIX-03 → 修改 combine.py 震荡金叉死叉分支

第 2 批 (High, 依赖第 1 批):
  FIX-07 → 新增 MA5 + 修改 rsi_signals.py（需先有 ma.py 变更）
  FIX-08 → 修改 rsi_signals.py + combine.py（依赖 FIX-02 阈值结构）
  FIX-06 → 修改 combine.py 下降趋势分支
  FIX-09 → 修改 control.py + strategy.yaml
  FIX-10 → 修改 combine.py 背离分支

第 3 批 (Medium, 依赖第 2 批):
  FIX-13 → 新增 MA20
  FIX-12 → 修改 control.py（依赖 FIX-08 阈值结构）
  FIX-11 → 修改 combine.py + runner.py（依赖完整信号逻辑就绪）
```

---

## 八、风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| combine.py 重写引入回归问题 | 修正前导出 v2 全量回测基线，修正后对比 |
| 更严格过滤导致信号过少 | 通过回测验证信号数量和胜率平衡；必要时微调阈值 |
| 新参数传递链路长（yaml→strategy→combine→rsi_signals） | 通过集成测试覆盖完整链路 |
| 震荡市金叉缩量规则可能过于严格 | 保持 v2 的趋势内金叉逻辑不变，仅震荡市调整 |

---

## 九、检查点

| 检查项 | 状态 |
|--------|------|
| 架构设计（分层不变） | 已确认 |
| 接口变更（向后兼容） | 已确认 |
| 数据流（新增 MA5/MA20） | 已设计 |
| 配置变更（向后兼容） | 已设计 |
| 测试方案（覆盖 13 条 FIX） | 已设计 |
| 实施顺序（依赖关系） | 已规划 |

---

**下一步**：确认后进入「步骤 5：开发步骤拆分」，将以上设计拆解为具体的开发任务清单。
