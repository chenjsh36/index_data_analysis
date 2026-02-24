# 技术方案设计（TDD）— v8 纳指 50日均线+成交量+RSI 三合一策略

**文档类型**：技术设计（步骤 4）  
**依据**：`docs/v8/02-requirements-documentation.md`、`docs/v8/brd.md`  
**策略名**：**NDX_MA50_Volume_RSI**；趋势与信号规则完全按 BRD 执行

---

## 1. 系统架构概览

v8 在现有 **index_data_analysis** 内扩展：新增一个策略类、数据准备分支、报告分支。**不新增指标模块**（复用 `calculate_ma`、`calculate_rsi_handwrite`、`calculate_volume_ratio`）。

### 1.1 模块与职责

| 模块 | 路径 | 职责（v8 相关） |
|------|------|-----------------|
| 指标层 | `ndx_rsi/indicators/` | 复用 `ma.calculate_ma(close, 50)`、`rsi.calculate_rsi_handwrite(close, 14)`、`volume_ratio.calculate_volume_ratio(volume, 20)`；不在指标层新增接口 |
| 策略层 | `ndx_rsi/strategy/ndx_ma50_volume_rsi.py`（新建） | 新增 `NDXMA50VolumeRSIStrategy`：BRD 第三步趋势判定、第四步 RSI+量能信号、`generate_signal` / `calculate_risk` |
| 工厂 | `ndx_rsi/strategy/factory.py` | 策略名 `NDX_MA50_Volume_RSI` → `NDXMA50VolumeRSIStrategy(config)` |
| 数据准备 | `ndx_rsi/backtest/runner.py`、`ndx_rsi/cli_main.py` | 对 `NDX_MA50_Volume_RSI` 分支：计算并写入 `ma50`、`rsi_14`、`volume_ratio`；SMA50 斜率在策略内按需计算 |
| 报告 | `ndx_rsi/report/signal_report.py` | 新增 `_report_ndx_ma50_volume_rsi`；`format_signal_report` 增加 NDX_MA50_Volume_RSI 分支 |
| 配置 | `config/strategy.yaml` | 新增 `strategies.NDX_MA50_Volume_RSI` 段 |

### 1.2 数据流（NDX_MA50_Volume_RSI）

```
  OHLCV (close, volume)
         |
         v
  +------+------+  策略名 == "NDX_MA50_Volume_RSI"
  | 数据准备      |  ma50, rsi_14, volume_ratio
  +------+------+
         |
         v
  +------+------+
  | 策略         |  策略内：SMA50 斜率、趋势类型（BRD 第三步）
  | NDXMA50...   |  generate_signal(data) → sig（BRD 第四步）
  |              |  calculate_risk(sig, data) → risk
  +------+------+
         |
         v
  +------+------+
  | 报告         |  format_signal_report("NDX_MA50_Volume_RSI", ...) → 文本
  +------+------+
```

---

## 2. 指标与列约定（复用）

| 指标 | 来源 | 列名 | 说明 |
|------|------|------|------|
| SMA50 | `calculate_ma(close, 50)` | `ma50`（与现有 NDX_short 一致） | 50 日简单移动均线 |
| RSI(14) | `calculate_rsi_handwrite(close, 14)` | `rsi_14` | BRD 主 RSI |
| 20 日均量比 | `calculate_volume_ratio(volume, 20)` | `volume_ratio` | 放量 ≥1.2、缩量 ≤0.8 |
| SMA50 斜率 | 策略内计算 | 不写回 DataFrame，仅用于当日趋势判定 | `sma50_slope_pct = (sma50[i]-sma50[i-1])/sma50[i-1]*100` |

---

## 3. 策略层设计

### 3.1 策略类：NDXMA50VolumeRSIStrategy

- **位置**：新建 `ndx_rsi/strategy/ndx_ma50_volume_rsi.py`（与 ndx_short、ema_cross 并列）。
- **继承**：`BaseTradingStrategy`。
- **配置**（从 `self.config` 读取，与需求/BRD 一致）：
  - `index_code`（默认 "QQQ"）
  - `rsi_period`（默认 14）
  - `vol_ratio_heavy`（默认 1.2，放量阈值）
  - `vol_ratio_light`（默认 0.8，缩量阈值）
  - `slope_flat_threshold`（默认 0.1）：震荡判定用——连续 5 日 SMA50 斜率绝对值小于该阈值即视为走平。**单位为「百分比数值」**：0.1 表示 **0.1%**（即 0.1 个百分点），不是 10%；与 BRD 伪代码中 `abs(sma50_slope_pct) < 0.1` 一致。
  - `oscillate_range`（默认 0.03）：震荡判定用——收盘价在 SMA50 的 ± 该比例内，即 [SMA50×(1-0.03), SMA50×(1+0.03)]，即 ±3%。
  - **风控参数**（供 `calculate_risk` 使用）：
    - `risk_control.stop_loss_ratio`（如 0.05）：相对**当日收盘价**的止损比例，即止损价 = close×(1 - 该值)，如 5% 止损。
    - `risk_control.take_profit_ratio`（如 0.20）：相对**当日收盘价**的止盈比例，即止盈价 = close×(1 + 该值)，如 20% 止盈。
    - `stop_below_ma50_pct`（可选，默认 0.02）：当操作建议为「止损 MA50 下方」时使用，表示止损价 = MA50×(1 - 该值)，即 MA50 **下方 2%**。
    - `stop_below_ma20_pct`（可选，默认 0.03）：当操作建议为「止损 MA20 下方」时使用，表示止损价 = MA20×(1 - 该值)，即 MA20 **下方 3%**。

### 3.2 趋势判定（BRD 第三步，严格按伪代码）

- **输入**：当前行及前若干行的 `close`、`ma50`；策略内计算当前及前 4 日的 `sma50_slope_pct`（需至少 5 日 SMA50，即从第 54 根 K 线起可判震荡）。
- **最小数据长度**：为同时满足「连续 3 日 SMA50」「连续 5 日斜率」「连续 2 日收盘」，至少需要 **55 根 K 线**（索引 0..54，当前为 54 时可算斜率 50..54）。实现时建议 **loop_start = 60**，与需求「建议 60」一致。
- **上升趋势**（优先级最高）：
  - `condition_up_1`：`close[i] > ma50[i]`
  - `condition_up_2`：`ma50[i] > ma50[i-1] > ma50[i-2] > ma50[i-3]`（连续 3 日向上）
  - `condition_up_3`：非「连续 2 日收盘跌破」：`not (close[i] < ma50[i] and close[i-1] < ma50[i-1])`
  - 三者皆真 → `trend_type = "上升趋势"`
- **下降趋势**：
  - `condition_down_1`：`close[i] < ma50[i]`
  - `condition_down_2`：`ma50[i] < ma50[i-1] < ma50[i-2] < ma50[i-3]`
  - `condition_down_3`：非「连续 2 日收盘站上」：`not (close[i] > ma50[i] and close[i-1] > ma50[i-1])`
  - 三者皆真 → `trend_type = "下降趋势"`
- **震荡趋势**（仅当上升、下降均不满足时）：
  - `condition_shock_1`：连续 5 日 `abs(sma50_slope_pct) < 0.1`（使用 config 的 `slope_flat_threshold`）
  - `condition_shock_2`：`sma50[i] * 0.97 <= close[i] <= sma50[i] * 1.03`（使用 config 的 `oscillate_range`）
  - 两者皆真 → `trend_type = "震荡趋势"`
- **趋势过渡**：以上均不满足 → `trend_type = "趋势过渡（无明确方向）"`（或简写为 `"趋势过渡"`，报告可统一展示）

### 3.3 RSI+成交量信号（BRD 第四步，严格按伪代码）

- **输入**：当日 `trend_type`、`rsi_14`、`volume_ratio`。
- **上升趋势**：
  - `40 <= rsi_14 <= 50` 且 `volume_ratio <= vol_ratio_light` → 有效加仓，`reason="bull_pullback_volume_ok"`，`position` 建议 0.35（约 30–40%）
  - `70 <= rsi_14 <= 80` 且 `volume_ratio <= vol_ratio_light` → 轻仓减仓，`reason="bull_overbought_volume_weak"`，`position` 建议 0.25
  - `rsi_14 > 80` 且 `volume_ratio >= vol_ratio_heavy` → 继续持仓，`reason="bull_overbought_volume_ok"`，`position=1.0`
  - 其余 → 观望/维持，`reason="bull_hold"` 等，`position` 可依当前仓位或 1.0（上升趋势默认偏多）
- **下降趋势**：
  - `50 <= rsi_14 <= 60` 且 `volume_ratio >= vol_ratio_heavy` → 减仓，`reason="bear_rally_volume_heavy"`，`position` 建议 0.5
  - `20 <= rsi_14 <= 30` 且 `volume_ratio <= vol_ratio_light` → 轻仓试多，`reason="bear_oversold_volume_light"`，`position` 建议 0.3
  - `rsi_14 < 20` 且 `volume_ratio >= vol_ratio_heavy` → 观望不抄底，`reason="bear_oversold_no_bottom"`，`position=0.0`
  - 其余 → 观望，`position=0.0` 或维持
- **震荡趋势**：
  - `65 <= rsi_14 <= 70` 且 `volume_ratio >= vol_ratio_heavy` → 减仓，`reason="osc_sell"`，`position` 建议 0.6
  - `30 <= rsi_14 <= 35` 且 `volume_ratio <= vol_ratio_light` → 加仓，`reason="osc_buy"`，`position` 建议 0.35
  - 其余 → 观望
- **趋势过渡**：`reason="transition"`，`position=0.0` 或保持前一状态（实现时可统一为观望 `position=0.0`）

### 3.4 generate_signal 返回值约定

- 返回 `Dict[str, Any]`，至少包含：
  - `"signal"`：`"buy"` | `"sell"` | `"hold"`
  - `"position"`：`float`，0.0～1.0
  - `"reason"`：字符串，与上述 reason 及报告展示一致
  - 可选：`"trend_type"`（上升趋势/下降趋势/震荡趋势/趋势过渡）、`"operation"`（BRD 原文操作建议，如「加仓30-40%，止损MA50下方2%」），便于报告直接使用

### 3.5 calculate_risk

- 根据 `reason` 与 config 的 `risk_control` 返回 `{"stop_loss": float, "take_profit": float}`。
- 止损可依 reason 选用：BRD 中「止损 MA50 下方 2%」→ 用 `close * (1 - stop_below_ma50_pct)`；「止损 MA20 下方 3%」→ 若有 ma20 列则用 `ma20 * (1 - stop_below_ma20_pct)`，否则用比例止损。
- 默认与现有策略一致：`stop_loss = close * (1 - stop_loss_ratio)`，`take_profit = close * (1 + take_profit_ratio)`。

---

## 4. 工厂与配置

### 4.1 工厂

- **文件**：`ndx_rsi/strategy/factory.py`
- **修改**：
  - `from ndx_rsi.strategy.ndx_ma50_volume_rsi import NDXMA50VolumeRSIStrategy`
  - `if strategy_name == "NDX_MA50_Volume_RSI": return NDXMA50VolumeRSIStrategy(config)`

### 4.2 配置

- **文件**：`config/strategy.yaml`
- **新增**：在 `strategies:` 下增加：

```yaml
  NDX_MA50_Volume_RSI:
    index_code: "QQQ"
    rsi_period: 14
    vol_ratio_heavy: 1.2
    vol_ratio_light: 0.8
    slope_flat_threshold: 0.1    # 震荡：连续5日斜率绝对值 < 0.1%（单位：百分比数值，0.1 即 0.1%）
    oscillate_range: 0.03        # 震荡：收盘在 SMA50 ±3%
    risk_control:
      stop_loss_ratio: 0.05
      take_profit_ratio: 0.20
    # 可选，用于与 BRD 文案对齐的止损
    # stop_below_ma50_pct: 0.02
    # stop_below_ma20_pct: 0.03
```

---

## 5. 数据准备

### 5.1 回测 runner

- **文件**：`ndx_rsi/backtest/runner.py`
- **新增分支**：`elif strategy_name == "NDX_MA50_Volume_RSI":`
  - 计算并写入：`df["ma50"] = calculate_ma(df["close"], 50)`，`df["rsi_14"] = calculate_rsi_handwrite(df["close"], 14)`，`df["volume_ratio"] = calculate_volume_ratio(df["volume"], 20)`。
  - `loop_start = 60`（保证趋势与斜率所需最少 55+ 的窗口）。
  - 若 `len(df) < loop_start`，返回 `{"error": "insufficient_data", ...}`。
- **导入**：确保已导入 `calculate_ma`、`calculate_rsi_handwrite`、`calculate_volume_ratio`（与 NDX_short 分支一致）。

### 5.2 run_signal（cli_main）

- **文件**：`ndx_rsi/cli_main.py` 的 `cmd_run_signal`。
- **修改**：
  - 将拉取更长历史的策略列表中加入 `"NDX_MA50_Volume_RSI"`（例如与 NDX_short 一样拉取约 60～120 日，或与 EMA 一样 400 日均可，至少 60 日）。
  - 新增 `elif strategy_name == "NDX_MA50_Volume_RSI":`：计算 `ma50`、`rsi_14`、`volume_ratio`，与 runner 一致；`min_bars = 60`，不足则提示并 return 1。
- **调用**：`sig = strategy.generate_signal(df)`（无需额外参数）。

---

## 6. 报告层设计

### 6.1 文本报告 _report_ndx_ma50_volume_rsi

- **文件**：`ndx_rsi/report/signal_report.py`
- **函数**：`_report_ndx_ma50_volume_rsi(symbol, row, date_str, sig, risk, config) -> str`
- **格式**（与需求 2.8 一致）：
  - 分隔线、标题：`【{symbol} NDX_MA50_Volume_RSI 信号 - {date_str}】`
  - 收盘价、SMA50（来自 `row["close"]`、`row["ma50"]`）
  - 趋势类型（来自 `sig.get("trend_type", "—")`）
  - RSI(14)、成交量比值（来自 `row["rsi_14"]`、`row["volume_ratio"]`）
  - 推导逻辑（根据 `sig["reason"]` 或 trend_type + RSI + 量能 生成一句总结）
  - 操作建议（`sig.get("operation")` 或 `sig["reason"]`）
  - 止损、止盈（`risk["stop_loss"]`、`risk["take_profit"]`）

### 6.2 format_signal_report 分支

- 在 `format_signal_report` 中增加：`if strategy_name == "NDX_MA50_Volume_RSI": return _report_ndx_ma50_volume_rsi(...)`。

---

## 7. 接口与数据约定汇总

| 接口/数据 | 约定 |
|-----------|------|
| DataFrame 列名（NDX_MA50_Volume_RSI） | `ma50`, `rsi_14`, `volume_ratio`（必须）；`close`, `volume`（OHLCV 必有） |
| 策略内斜率 | 不要求写入列；`sma50_slope_pct[i] = (ma50[i]-ma50[i-1])/ma50[i-1]*100`，需至少 5 日用于震荡判定 |
| 最小 K 线数 | 60（loop_start=60；趋势+斜率需约 55） |
| `generate_signal` 返回 | `signal`, `position`, `reason`；可选 `trend_type`, `operation` |
| trend_type 取值 | `"上升趋势"` \| `"下降趋势"` \| `"震荡趋势"` \| `"趋势过渡"`（或 `"趋势过渡（无明确方向）"`） |
| reason 示例 | `bull_pullback_volume_ok` \| `bull_overbought_volume_weak` \| `bear_rally_volume_heavy` \| `osc_sell` \| `transition` 等，与 BRD 操作一一对应 |

---

## 8. 风险与简化说明

| 项 | 说明 |
|----|------|
| 斜率列 | 不在数据准备阶段写入 `sma50_slope_pct`，由策略在当根 K 线计算最近 5 日斜率，减少列与 runner 耦合。 |
| position 精度 | 加仓/减仓/轻仓试多等用 0.35、0.5、0.3 等代表仓位比例，与现有 backtest 的仓位语义一致；若 runner 仅支持 0/1，可在 runner 内做二值化（如 position>=0.5 视为 1）。 |
| 趋势过渡 | 不持仓时 `position=0.0`，避免在无明确趋势时开仓。 |

---

## 9. 输出物与检查点

| 输出物 | 状态 |
|--------|------|
| 技术设计文档（本文档） | ✅ |
| 模块划分与数据流（第 1 节） | ✅ |
| 指标复用与列约定（第 2 节） | ✅ |
| 策略逻辑：趋势（第三步）+ 信号（第四步）（第 3 节） | ✅ |
| 工厂与配置（第 4 节） | ✅ |
| 数据准备与报告（第 5、6 节） | ✅ |
| 接口与数据约定（第 7 节） | ✅ |
| 文件名 | `04-technical-design.md`（本文档） |

- ✅ v8 无新指标模块、无新服务；设计限于新策略类、数据准备与报告扩展。
- ✅ 趋势与信号规则与 `docs/v8/brd.md` 伪代码一致，可直接进入步骤 5「开发步骤拆分」或编码实现。

**下一步**：完成本步骤后需用户确认；确认后进入步骤 5「开发步骤拆分」或直接开始编码。
