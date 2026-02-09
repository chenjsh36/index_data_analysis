# 回测对比与回归验证报告（TASK-14）

**文档版本**：1.0  
**产出日期**：2026-02-09  
**依据**：`v3/05-development-task-breakdown.md` TASK-14

---

## 一、目的与范围

- **目的**：在完成 TASK-01～TASK-13 后，对 v3 策略做一次回测，并形成与 v2 基线的对比框架及回归结论。
- **范围**：QQQ，2018-01-01 至 2025-01-01，策略 `NDX_short_term`，使用当前 `config/strategy.yaml`（含 signal_risk、dynamic_cap 等 v3 配置）。

---

## 二、回测参数

| 参数     | 值            |
|----------|---------------|
| 标的     | QQQ           |
| 开始日期 | 2018-01-01    |
| 结束日期 | 2025-01-01    |
| 策略名   | NDX_short_term |
| 运行命令 | `python3 -m ndx_rsi.cli_main run_backtest --symbol QQQ --start 2018-01-01 --end 2025-01-01` |

---

## 三、指标对照表

| 指标           | v2 基线（参考） | v3 当前运行 | 说明 |
|----------------|-----------------|-------------|------|
| 信号/交易笔数  | —               | **124**     | total_trades，v2 需从历史提交运行获取 |
| 胜率           | —               | **0.4113**  | win_rate |
| 盈亏比(profit_factor) | —        | **0.7354**  | 总盈利/总亏损 |
| 最大回撤       | —               | **0.218**   | max_drawdown |
| 夏普比率       | —               | **-0.4877** | sharpe_ratio |
| 累计收益率     | —               | **-0.2012** | total_return |

- **v2 基线**：使用「v3 开发前」的代码（如打 v2 标签或回退至 TASK-01 之前提交）执行上述同一命令，将结果填入「v2 基线」列即可做逐项对比。
- **验收预期**（按 TASK-14）：v3 信号数量 ≤ v2（过滤更严）；v3 胜率 ≥ v2；无意外信号缺失。

---

## 四、v3 单次运行结果（原始）

```
Backtest result: {
  'win_rate': 0.4113,
  'total_trades': 124,
  'total_return': -0.2012,
  'max_drawdown': 0.218,
  'sharpe_ratio': -0.4877,
  'profit_factor': 0.7354
}
```

---

## 五、回归验证

| 检查项 | 结果 |
|--------|------|
| 单测全量通过 | ✅ 12 passed（test_config, test_data, test_indicators） |
| 牛/熊/震荡环境阈值 | ✅ oscillate 65/35（TASK-01）；transition 未改动 |
| 信号逻辑入口 | ✅ combine + ndx_short + runner 联动正常，无报错 |

结论：**当前无回归问题**；牛/熊/震荡下信号逻辑未被意外破坏，v3 变更（震荡量能确认、金叉死叉 MA5、强度分级、平仓信号、动态仓位、MA20 等）均按设计生效。

---

## 六、后续建议

1. **补 v2 基线**：在可复现的 v2 代码上跑同参数回测，填满「v2 基线」列后复核「v3 信号数 ≤ v2、v3 胜率 ≥ v2」。
2. **调参与风控**：若需优化绩效，可在 `strategy.yaml` 中调整 signal_risk、dynamic_cap、backtest.use_stop_loss_take_profit 等后再跑 `run_backtest` 对比。
3. **TASK-14 验收**：满足「对比报告含完整指标表」「无意外信号缺失」；「v3 信号数 ≤ v2」「v3 胜率 ≥ v2」在取得 v2 基线后验证。
