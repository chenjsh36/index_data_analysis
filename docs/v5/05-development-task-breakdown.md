# 开发步骤拆分（Development Task Breakdown）— v5 信号可读化与推导逻辑展示

**文档版本**：1.0  
**产出日期**：2026-02-12  
**依据**：研发流程步骤 5 - 开发步骤拆分  
**上游输入**：`v5/04-technical-design.md`

---

## 一、里程碑计划

| 里程碑 | 包含任务 | 目标 |
|--------|----------|------|
| **M1 — 报告模块** | TASK-01 | 新建 report 模块，实现 format_signal_report 及三策略报告与推导逻辑 |
| **M2 — CLI 接入** | TASK-02 | cmd_run_signal 改为调用报告格式化并打印，不再输出 raw dict |

---

## 二、任务依赖图

```
TASK-01 (report 模块 + 三策略报告与推导模板)
   │
   └──→ TASK-02 (cli_main 调用 format_signal_report 并 print)
```

---

## 三、任务清单

### TASK-01: 新建 report 模块并实现可读报告与推导逻辑

| 字段 | 内容 |
|------|------|
| **ID** | TASK-01 |
| **名称** | 新建 report 模块并实现可读报告与推导逻辑 |
| **优先级** | P0 |
| **对应需求** | FR-V5-01, FR-V5-02, FR-V5-03 |
| **估算** | M (1 天) |
| **依赖** | 无 |
| **描述** | 1. 新建 `ndx_rsi/report/` 包，包含 `__init__.py` 与 `signal_report.py`。2. 实现 `format_signal_report(strategy_name, symbol, df, sig, risk, strategy_config=None) -> str`：取 row=df.iloc[-1]、date=df.index[-1]；按 strategy_name 分支。3. **EMA_cross_v1**：展示日期、收盘价、EMA50、EMA200、推导逻辑（按 reason：golden_cross/death_cross/hold/monthly_rebalance 选模板并填数）、操作建议、止损、止盈。4. **EMA_trend_v2**：展示日期、收盘价、EMA80、EMA200、20日波动率、阈值、推导逻辑（趋势+波动率→建议）、操作建议、止损、止盈。5. **NDX_short_term**：展示日期、收盘价、MA50、RSI(9)、RSI(24)、量能比、推导逻辑（按 reason 映射简短中文）、操作建议、止损、止盈。6. 版式：分隔线 55、标题【{symbol} {策略显示名} 信号 - {date}】、多行「  标签: 数值」、结尾分隔线。7. 可选实现 `print_signal_report(...)` 内部 format 后 print。 |
| **涉及文件** | `ndx_rsi/report/__init__.py`（新建）、`ndx_rsi/report/signal_report.py`（新建） |
| **验收标准** | 1. 给定含 ema_80、ema_200、vol_20 的 df 与 sig reason=uptrend_low_vol，返回字符串含「上升趋势」「低波动」「满仓」及对应数值。2. 给定 EMA_cross_v1 的 df 与 reason=golden_cross，返回字符串含「黄金交叉」「建议买入」。3. NDX_short_term 的 df 与某 reason 返回含推导逻辑与操作建议。4. 三种策略均无 KeyError（缺失列用 N/A 或跳过）。 |

---

### TASK-02: CLI 接入可读报告

| 字段 | 内容 |
|------|------|
| **ID** | TASK-02 |
| **名称** | CLI 接入可读报告 |
| **优先级** | P0 |
| **对应需求** | FR-V5-01 |
| **估算** | XS (0.25 天) |
| **依赖** | TASK-01 |
| **描述** | 在 `ndx_rsi/cli_main.py` 的 `cmd_run_signal` 中，在得到 sig、risk 后不再 `print("Signal:", sig)`、`print("Risk:", risk)`；改为调用 `format_signal_report(strategy_name, args.symbol, df, sig, risk, get_strategy_config(strategy_name))`，得到字符串后 `print(报告)`。 |
| **涉及文件** | `ndx_rsi/cli_main.py` |
| **验收标准** | 1. 执行 `run_signal --strategy EMA_trend_v2 --symbol QQQ` 输出为可读报告（分行、带标签、含推导逻辑），无 raw dict。2. EMA_cross_v1、NDX_short_term 同理。3. 程序化获取 sig/risk 的调用方若依赖返回值，当前 cmd_run_signal 无返回值变更（仅打印内容变化）。 |

---

## 四、任务汇总与排期

| 任务 | 优先级 | 估算 | 依赖 | 里程碑 |
|------|--------|------|------|--------|
| TASK-01 report 模块与三策略报告/推导 | P0 | M | 无 | M1 |
| TASK-02 CLI 接入 | P0 | XS | T01 | M2 |

**总估算**：约 1.25 天

---

## 五、检查点

| 检查项 | 状态 |
|--------|------|
| 任务粒度适中 | 已确认 |
| 每任务有验收标准 | 已确认 |
| 依赖关系已识别 | 已确认 |

---

**下一步**：按 TASK-01 → TASK-02 顺序实现（步骤 6：代码开发）。
