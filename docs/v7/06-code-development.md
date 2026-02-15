# 代码开发记录（步骤 6）— v7 纳指机构级策略

**文档类型**：开发实现记录  
**依据**：`docs/v7/05-development-task-breakdown.md`、`docs/v7/04-technical-design.md`

---

## 1. 实现清单与文件映射

| 任务 ID | 实现内容 | 文件/位置 |
|---------|----------|------------|
| T1 | ADX(14) 手写 | `ndx_rsi/indicators/adx.py`：`calculate_adx(high, low, close, period=14)`，Wilder 平滑 |
| T1 | MACD(12,26,9) 手写 | `ndx_rsi/indicators/macd.py`：`calculate_macd(close, fast, slow, signal)` 返回 (macd_line, signal_line, histogram) |
| T1 | 导出 | `ndx_rsi/indicators/__init__.py`：增加 `calculate_adx`、`calculate_macd` |
| T2 | EMATrendV3Strategy | `ndx_rsi/strategy/ema_cross.py`：五条件、可选 VIX/vol_20、generate_signal(**kwargs)、calculate_risk |
| T3 | 工厂 | `ndx_rsi/strategy/factory.py`：`EMA_trend_v3` → `EMATrendV3Strategy(config)` |
| T3 | 配置 | `config/strategy.yaml`：`strategies.EMA_trend_v3` 段（ema_fast/slow、adx、macd、vol、vix_threshold、risk_control） |
| T4 | 回测数据准备 | `ndx_rsi/backtest/runner.py`：`elif strategy_name == "EMA_trend_v3"`，计算 ema_80/200、vol_20、sma_200、adx_14、macd_line，loop_start=200 |
| T5 | run_signal 数据准备 | `ndx_rsi/cli_main.py`：拉取 400 日、`elif strategy_name == "EMA_trend_v3"` 同 runner 列，min_bars=200 |
| T6 | 报告 v3 | `ndx_rsi/report/signal_report.py`：`_report_ema_trend_v3`、`format_signal_report` 分支、`signal_report_to_dict` 分支（含 conditions_met） |
| T7 | 脚本 | `scripts/run_signal_and_notify.py`：EMA_trend_v3 数据准备分支；`scripts/generate_static_data.py`：EMA_trend_v3 数据准备与 signal_report_to_dict 支持 |

---

## 2. 使用方式

### 2.1 跑信号（CLI）

```bash
# 从项目根
PYTHONPATH=. python -m ndx_rsi.cli_main run_signal --symbol QQQ --strategy EMA_trend_v3
```

### 2.2 回测

```bash
PYTHONPATH=. python -m ndx_rsi.cli_main run_backtest --strategy EMA_trend_v3 --symbol QQQ
```

### 2.3 通知脚本（环境变量 STRATEGY=EMA_trend_v3）

```bash
STRATEGY=EMA_trend_v3 PYTHONPATH=. python scripts/run_signal_and_notify.py
```

### 2.4 静态数据生成

```bash
PYTHONPATH=. python scripts/generate_static_data.py --strategy EMA_trend_v3 --out-dir web
```

---

## 3. 验收核对

- [x] ADX、MACD 可计算并导出；SMA200 复用 calculate_ma。
- [x] 策略 EMA_trend_v3 注册；五条件全满足才 position=1.0；reason 区分未满足项。
- [x] 回测与 run_signal 中 v3 分支计算所需列；loop_start/min_bars=200。
- [x] 报告含收盘价、EMA、SMA200、ADX、MACD、五条件、推导逻辑、操作建议、止损止盈。
- [x] signal_report_to_dict 对 v3 返回 conditions_met、sma_200、adx_14、macd_line 等。
- [x] 脚本 run_signal_and_notify、generate_static_data 支持 EMA_trend_v3。

---

## 4. 变更日志

| 日期 | 说明 |
|------|------|
| 2025-02-15 | v7 初版：指标 ADX/MACD、策略 EMATrendV3、数据准备、报告、脚本分支、配置与工厂 |
