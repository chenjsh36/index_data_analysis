# 开发步骤拆分（步骤 5）— v7 纳指机构级策略

**文档类型**：开发任务拆分  
**依据**：`docs/v7/04-technical-design.md`  
**参考规范**：WBS、INVEST、Story Points

---

## 1. 任务清单（Task List）

| ID | 任务名称 | 描述 | 验收标准 | 依赖 | 估算 | 优先级 |
|----|----------|------|----------|------|------|--------|
| T1 | 指标层 ADX、MACD | 新增 `ndx_rsi/indicators/adx.py`（calculate_adx）、`macd.py`（calculate_macd）；在 `__init__.py` 中导出 | 单元测试或手测：给定 high/low/close 能输出与公式一致的 ADX、MACD 序列 | 无 | 2 | P0 |
| T2 | 策略类 EMATrendV3Strategy | 在 `ema_cross.py` 中新增 EMATrendV3Strategy：五条件判断、可选 VIX/vol_20、generate_signal、calculate_risk | 给定含所需列的 df，返回正确 signal/position/reason；缺列返回 missing_indicators | T1 | 2 | P0 |
| T3 | 工厂与配置 | factory.py 增加 EMA_trend_v3 分支；strategy.yaml 增加 EMA_trend_v3 配置段 | create_strategy("EMA_trend_v3") 返回实例；config 可被策略读取 | T2 | 1 | P0 |
| T4 | 回测数据准备 | runner.py 中增加 elif strategy_name == "EMA_trend_v3" 分支：计算 ema_80/200、vol_20、sma_200、adx_14、macd_line；loop_start=200 | run_backtest(strategy_name="EMA_trend_v3") 可运行且无缺列报错 | T1,T3 | 1 | P0 |
| T5 | run_signal 数据准备 | cli_main.py 中 run_signal 增加 EMA_trend_v3 分支：拉取 400 日、计算同 runner 的列、min_bars=200 | `run_signal --strategy EMA_trend_v3 --symbol QQQ` 输出报告 | T4 | 1 | P0 |
| T6 | 信号报告 v3 | signal_report.py 新增 _report_ema_trend_v3、format_signal_report 分支、signal_report_to_dict 分支；输出五条件满足情况、推导逻辑等 | 报告含收盘价/EMA/SMA200/ADX/MACD、五条件、操作建议、止损止盈 | T2 | 2 | P0 |
| T7 | 脚本分支 | run_signal_and_notify.py、generate_static_data.py 中为 EMA_trend_v3 增加数据准备与策略分支（与 cli_main 一致） | STRATEGY=EMA_trend_v3 时脚本可正常跑信号并产出报告/JSON | T5,T6 | 1 | P1 |
| T8 | 文档 06-code-development | 新增 docs/v7/06-code-development.md，记录实现项与使用方式 | 文档可追溯 T1～T7 实现位置与验收 | T7 | 1 | P1 |

---

## 2. 任务依赖图（Dependency Graph）

```
    T1 ──> T2 ──> T3
    T1 ──> T4
    T3 ──> T4
    T4 ──> T5 ──> T7
    T2 ──> T6
    T6 ──> T7 ──> T8
```

- T1 先做；T2 依赖 T1；T3 依赖 T2；T4 依赖 T1、T3；T5 依赖 T4；T6 依赖 T2；T7 依赖 T5、T6；T8 依赖 T7。

---

## 3. 开发计划与里程碑

| 里程碑 | 包含任务 | 目标 |
|--------|----------|------|
| M1：指标与策略可用 | T1, T2, T3 | ADX/MACD 可算、v3 策略可实例化并出信号 |
| M2：回测与 run_signal 可用 | T4, T5, T6 | 回测与 CLI run_signal 支持 EMA_trend_v3，报告完整 |
| M3：脚本与文档收尾 | T7, T8 | 脚本支持 v3、06 文档就绪 |

---

## 4. 输出物

- 任务清单（上表）
- 任务依赖图（第 2 节）
- 开发计划/里程碑（第 3 节）
- 文件名：`05-development-task-breakdown.md`（本文档）

**下一步**：按 T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 顺序执行步骤 6（代码开发）。
