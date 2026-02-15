# 技术方案设计（TDD）— v7 纳指机构级策略

**文档类型**：技术设计（步骤 4）  
**依据**：`docs/v7/02-requirements-documentation.md`、`docs/v7/03-technology-stack-selection.md`  
**参考规范**：分层架构、接口约定、与现有 ndx_rsi 一致

---

## 1. 系统架构概览

v7 仅在现有 **index_data_analysis** 内扩展：新增指标模块、新策略类、数据准备分支、报告分支。不新增服务、UI 或外部 API。

### 1.1 模块与职责

| 模块 | 路径 | 职责（v7 相关） |
|------|------|-----------------|
| 指标层 | `ndx_rsi/indicators/` | 新增 `adx.py`、`macd.py`；导出 `calculate_adx`、`calculate_macd`；SMA200 复用 `ma.calculate_ma(series, 200)` |
| 策略层 | `ndx_rsi/strategy/ema_cross.py`（或单独 `ndx_institutional.py`） | 新增 `EMATrendV3Strategy`：五条件判断、可选 VIX/vol_20、`generate_signal` / `calculate_risk` |
| 工厂 | `ndx_rsi/strategy/factory.py` | 策略名 `EMA_trend_v3` → `EMATrendV3Strategy(config)` |
| 数据准备 | `ndx_rsi/backtest/runner.py`、`ndx_rsi/cli_main.py`（及可选 `scripts/run_signal_and_notify.py` 等） | 对 `EMA_trend_v3` 分支：计算并写入 `ema_80`、`ema_200`、`vol_20`、`sma_200`、`adx_14`、`macd_line` |
| 报告 | `ndx_rsi/report/signal_report.py` | 新增 `_report_ema_trend_v3`；`format_signal_report`、可选 `signal_report_to_dict` 增加 v3 分支 |
| 配置 | `config/strategy.yaml` | 新增 `strategies.EMA_trend_v3` 段 |

### 1.2 数据流（v3 策略）

```
  OHLCV (close, high, low, volume)
         |
         v
  +------+------+  策略名 == "EMA_trend_v3"
  | 数据准备      |  ema_80, ema_200, vol_20, sma_200, adx_14, macd_line
  +------+------+
         |
         v
  +------+------+
  | 策略         |  generate_signal(data, vix=?) → sig
  | EMATrendV3   |  calculate_risk(sig, data) → risk
  +------+------+
         |
         v
  +------+------+
  | 报告         |  format_signal_report("EMA_trend_v3", ...) → 文本
  |              |  signal_report_to_dict("EMA_trend_v3", ...) → dict（可选）
  +------+------+
```

---

## 2. 指标层设计

### 2.1 ADX（14 日）

- **文件**：`ndx_rsi/indicators/adx.py`
- **函数**：`calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series`
- **公式**（手写）：
  - +DM = high - high.shift(1)；-DM = low.shift(1) - low；TR = max(high-low, |high-close_prev|, |low-close_prev|)
  - 负的 DM 置 0；若 +DM > -DM 则 -DM=0，反之 +DM=0
  - Wilder 平滑（约等于 EMA alpha=1/period）：对 TR、+DM、-DM 做平滑得 ATR、+DI、-DI
  - DX = 100 * |+DI - -DI| / (+DI + -DI)；ADX = DX 的 period 日 Wilder 平滑
- **返回值**：与输入同索引的 Series，前若干行为 NaN（至少 period*2 左右才稳定）
- **导出**：在 `ndx_rsi/indicators/__init__.py` 中增加 `calculate_adx`；可选 `calculate_adx_talib`、`verify_adx`（未安装 TA-Lib 时跳过）

### 2.2 MACD（12, 26, 9）

- **文件**：`ndx_rsi/indicators/macd.py`
- **函数**：`calculate_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[pd.Series, pd.Series, pd.Series]`
  - 返回 `(macd_line, signal_line, histogram)`；策略仅用 **macd_line** 做 0 轴判断。
- **公式**：
  - ema_fast = close.ewm(span=fast, adjust=False).mean()
  - ema_slow = close.ewm(span=slow, adjust=False).mean()
  - macd_line = ema_fast - ema_slow
  - signal_line = macd_line.ewm(span=signal, adjust=False).mean()
  - histogram = macd_line - signal_line（可选，报告可展示）
- **导出**：在 `__init__.py` 中增加 `calculate_macd`；可选 TA-Lib 验证同 ADX。

### 2.3 SMA200

- **复用**：`ndx_rsi/indicators/ma.calculate_ma(series, 200)`，在数据准备中写入列 `sma_200`，不新增接口。

---

## 3. 策略层设计

### 3.1 策略类：EMATrendV3Strategy

- **位置**：与 v2 同文件 `ndx_rsi/strategy/ema_cross.py`，或单独 `ndx_institutional.py`（建议与 v2 同文件，保持 EMA 系列集中）。
- **继承**：`BaseTradingStrategy`。
- **配置**：从 `self.config` 读取（与 v2 对齐 + v3 独有）：
  - `ema_fast`（默认 80）、`ema_slow`（默认 200）
  - `adx_period`（默认 14）、`adx_threshold`（默认 25）
  - `macd_fast`（默认 12）、`macd_slow`（默认 26）、`macd_signal`（默认 9）
  - `vol_window`（默认 20）、`vol_threshold`（默认 0.02）
  - `use_vol_filter`（默认 false）：为 true 时需同时满足 vol_20 < vol_threshold
  - `vix_threshold`（默认 25）：仅当传入 vix 时使用
  - `risk_control.stop_loss_ratio`、`risk_control.take_profit_ratio`

### 3.2 generate_signal 逻辑

- **签名**：`generate_signal(self, data: pd.DataFrame, current_position_info: Optional[Dict] = None, vix: Optional[float] = None) -> Dict[str, Any]`
  - 若工厂/调用方不传 `vix`，则保持 `generate_signal(data, current_position_info)` 两参数兼容；vix 通过 config 注入或 kwargs 传入（需在 factory/runner 层适配）。
- **前置**：若 `data` 为空或行数不足 2，返回 `{"signal": "hold", "position": 0.0, "reason": "insufficient_data"}`。
- **列依赖**：`ema_80`、`ema_200`、`sma_200`、`adx_14`、`macd_line`（列名可来自 config，如 `ema_fast`→`ema_80`）。缺列则返回 `{"signal": "hold", "position": 0.0, "reason": "missing_indicators"}`。
- **做多依据**：仅**条件 1**（80EMA > 200EMA）决定是否做多；条件 2～5 仅作辅助参考，在报告中展示。
- **做多时**：若 80EMA > 200EMA（且可选 VIX、vol 过滤通过），则 `position=1.0`、`signal="buy"`；再根据五条件是否**全部**满足设置 `reason`：
  - 五条件全满足：`reason="all_conditions_met"`（报告展示**强烈买入**）；
  - 仅条件 1 满足：`reason="uptrend"`（报告为做多，其余条件供参考）。
- **不做多时**：`position=0.0`，reason 如 `ema_not_uptrend`、`vix_above_25`、`vol_above_threshold`。

### 3.3 calculate_risk

- 与 v2 一致：读取 `risk_control.stop_loss_ratio`（默认 0.05）、`take_profit_ratio`（默认 0.20），用最后一根 K 线 close 计算止损/止盈价并返回 `{"stop_loss": float, "take_profit": float}`。

---

## 4. 工厂与配置

### 4.1 工厂

- **文件**：`ndx_rsi/strategy/factory.py`
- **修改**：在 `create_strategy(strategy_name)` 中增加：
  - `if strategy_name == "EMA_trend_v3": return EMATrendV3Strategy(config)`
  - 并 `from ndx_rsi.strategy.ema_cross import ..., EMATrendV3Strategy`（或从 ndx_institutional 导入）。

### 4.2 配置

- **文件**：`config/strategy.yaml`
- **新增**：在 `strategies:` 下增加：

```yaml
  EMA_trend_v3:
    index_code: "QQQ"
    ema_fast: 80
    ema_slow: 200
    adx_period: 14
    adx_threshold: 25
    macd_fast: 12
    macd_slow: 26
    macd_signal: 9
    vol_window: 20
    vol_threshold: 0.02
    use_vol_filter: false   # 为 true 时启用 20 日波动率过滤
    vix_threshold: 25
    risk_control:
      stop_loss_ratio: 0.05
      take_profit_ratio: 0.20
```

- **列名约定**：数据准备阶段写入的列名与 config 对应：`ema_80`、`ema_200`、`sma_200`、`adx_14`、`macd_line`、`vol_20`（与 config 中 ema_fast/ema_slow/vol_window 一致）。

---

## 5. 数据准备

### 5.1 回测 runner

- **文件**：`ndx_rsi/backtest/runner.py`
- **位置**：在现有 `elif strategy_name == "EMA_trend_v2":` 之后增加 `elif strategy_name == "EMA_trend_v3":` 分支。
- **逻辑**：
  - 读取 config：ema_fast、ema_slow、vol_window、vol_threshold、adx_period、macd_fast、macd_slow、macd_signal（无则用默认值）。
  - 计算并写入：`df["ema_80"]`、`df["ema_200"]`（或按 config 的 ema_fast/ema_slow 动态列名）、`df["daily_return"]`、`df["vol_20"]`、`df["sma_200"] = calculate_ma(df["close"], 200)`、`df["adx_14"] = calculate_adx(df["high"], df["low"], df["close"], 14)`、`macd_line, _, _ = calculate_macd(df["close"], 12, 26, 9)` 并 `df["macd_line"] = macd_line`。
  - `loop_start = 200`（保证 SMA200 与 ADX/MACD 有足够历史数据）。
  - 若 `len(df) < loop_start`，返回 `{"error": "insufficient_data", ...}`。
- **导入**：在文件顶部增加 `calculate_adx`、`calculate_macd`、`calculate_ma`（若尚未导入）。

### 5.2 run_signal（cli_main）

- **文件**：`ndx_rsi/cli_main.py` 的 `cmd_run_signal`。
- **修改**：
  - 将 `strategy_name in ("EMA_cross_v1", "EMA_trend_v2")` 改为包含 `"EMA_trend_v3"`，以便 v3 也拉取约 400 日历史。
  - 在 `elif strategy_name == "EMA_trend_v2":` 后增加 `elif strategy_name == "EMA_trend_v3":`，计算与 runner 中**完全一致**的列（ema_80、ema_200、vol_20、sma_200、adx_14、macd_line）；`min_bars = 200`，不足则提示并 return 1。
- **调用策略**：`sig = strategy.generate_signal(df)`；若实现 VIX 传入，可在此处拉取 ^VIX 并 `sig = strategy.generate_signal(df, vix=vix_value)`。

### 5.3 其他入口

- 若 `scripts/run_signal_and_notify.py` 或 `scripts/generate_static_data.py` 会按策略名跑信号，需在其数据准备分支中同样增加对 `EMA_trend_v3` 的列计算（与 5.1、5.2 一致），避免缺列。

---

## 6. VIX（可选）

- **拉取**：在需要传 VIX 的调用点（如 `cmd_run_signal` 中策略名为 `EMA_trend_v3` 时），使用现有 `YFinanceDataSource` 或 yfinance 拉取 `^VIX` 最近 1 个交易日数据，取收盘或最后价。
- **传入**：通过 `generate_signal(df, vix=float)` 传入；或写入 `config["vix"]` 由策略读取（需在策略内约定 config 中 vix 键）。
- **策略内**：仅当 `vix is not None` 时判断 `vix < vix_threshold`；未传则视为通过。

---

## 7. 报告层设计

### 7.1 文本报告 _report_ema_trend_v3

- **文件**：`ndx_rsi/report/signal_report.py`
- **函数**：`_report_ema_trend_v3(symbol, row, date_str, sig, risk, config) -> str`
- **格式**：与 `_report_ema_trend_v2` 一致：分隔线 `"=" * 55`、标题 `【{symbol} 纳指机构级(v3) 信号 - {date_str}】`，然后按需求文档 2.6 顺序输出：
  - 收盘价、EMA80、EMA200、SMA200、ADX(14)（带阈值）、MACD 线（带 0 轴上方/下方）
  - **五条件满足情况**：逐条输出（条件1～5，可选 VIX、vol_20）
  - 推导逻辑（根据 sig["reason"] 生成一句总结）
  - 操作建议（`_action_from_position(sig)`）
  - 止损、止盈（`_build_common_tail`）
- **数据来源**：`row` 中取 `close`、`ema_80`、`ema_200`、`sma_200`、`adx_14`、`macd_line`、可选 `vol_20`；若 report 调用时传入 vix，可从 risk 或单独参数传入并在报告中展示。

### 7.2 format_signal_report 分支

- 在 `format_signal_report` 中增加：`if strategy_name == "EMA_trend_v3": return _report_ema_trend_v3(...)`。

### 7.3 signal_report_to_dict（可选）

- 在 `signal_report_to_dict` 中增加 `if strategy_name == "EMA_trend_v3":` 分支，返回 dict 包含：`date`, `symbol`, `strategy`, `close`, `ema_fast`, `ema_slow`, `sma_200`, `adx_14`, `macd_line`, `conditions_met`（列表或五条件布尔）, `derivation`, `action`, `stop_loss`, `take_profit`，以及可选 `vix`, `vol_20`, `vol_threshold`。

---

## 8. 接口与数据约定汇总

| 接口/数据 | 约定 |
|-----------|------|
| `calculate_adx(high, low, close, period=14)` | 返回 pd.Series，索引与 close 一致 |
| `calculate_macd(close, fast=12, slow=26, signal=9)` | 返回 (macd_line, signal_line, histogram) |
| DataFrame 列名（v3） | `ema_80`, `ema_200`, `vol_20`, `sma_200`, `adx_14`, `macd_line`（与 config 参数对应，可配置为动态列名） |
| `generate_signal` 返回 | `{"signal": "buy"|"sell"|"hold", "position": 0.0|1.0, "reason": str}` |
| reason 取值 | `all_conditions_met`（强烈买入） | `uptrend`（做多） | `ema_not_uptrend` | `vix_above_25` | `vol_above_threshold` | `missing_indicators` | `insufficient_data` |

---

## 9. 风险与简化说明

| 项 | 说明 |
|----|------|
| VIX | 本期为可选；不实现时策略仍可用，仅不做 VIX 过滤。 |
| ADX/MACD 验证 | 可选提供 TA-Lib 验证函数，未安装 TA-Lib 不影响运行。 |
| 列名 | 先固定为 ema_80、ema_200、adx_14、macd_line、sma_200、vol_20，与 config 默认一致；后续若有需要再做完全动态列名。 |

---

## 10. 输出物与检查点

| 输出物 | 状态 |
|--------|------|
| 技术设计文档（本文档） | ✅ |
| 模块划分与数据流（第 1 节） | ✅ |
| 指标 API（ADX、MACD、SMA200）（第 2 节） | ✅ |
| 策略逻辑与配置（第 3、4 节） | ✅ |
| 数据准备与报告（第 5、7 节） | ✅ |
| 接口与数据约定（第 8 节） | ✅ |
| 文件名 | `04-technical-design.md`（本文档） |

- ✅ v7 无 UI、无新服务，设计限于指标/策略/数据准备/报告扩展。
- ✅ 与现有 ndx_rsi 分层、配置、报告风格一致，可直接进入步骤 5「开发步骤拆分」。

**下一步**：完成本步骤后需用户确认；确认后进入步骤 5「开发步骤拆分」。
