# 回测空仓期按无风险利率计息（v4 增强）

**文档版本**：1.0  
**产出日期**：2026-02-12  
**涉及模块**：`ndx_rsi/backtest/runner.py`、`config/strategy.yaml`（backtest.metrics）

---

## 一、背景与问题

在原有回测逻辑中，**空仓（position = 0）时权益不变**，即空仓期间的日收益率为 0。这与实际情况不符：空仓资金通常以货币基金、短期国债等无风险或类无风险方式存放，会产生一定收益。若回测中空仓收益恒为 0，会：

- **低估策略真实收益**：长期空仓占比较高的策略，其“真实可比较”的总收益会被低估。
- **与夏普口径不一致**：夏普已用「年化收益 − 无风险利率」作分子，但权益曲线未体现空仓期的无风险增值，指标与曲线不完全对应。

因此需要在回测中**可选地**对空仓期按无风险利率计息，使权益曲线与绩效指标更贴近实际资金表现。

---

## 二、方案概述

- **空仓日**：在当日所有开平仓与止损止盈处理完成后，若 `position == 0` 且配置开启，则对当前权益按**日化无风险利率**复利一次：  
  `equity *= (1 + rfr_daily)`  
  其中 `rfr_daily = (1 + risk_free_rate)^(1/252) - 1`，`risk_free_rate` 为年化无风险利率（与夏普计算所用一致）。
- **bar_returns**：空仓日权益因计息而增加，故当日 `bar_returns` 自然包含该收益（`(equity - prev_equity) / prev_equity`），无需单独分支。
- **peak / max_drawdown**：计息后若 `equity > peak` 则更新 `peak`，并重新计算当日回撤，保证最大回撤与权益曲线一致。
- **开关**：通过配置项 `accrue_risk_free_when_flat` 控制是否启用；关闭时行为与改动前一致（空仓收益为 0）。

---

## 三、配置说明

在 `config/strategy.yaml` 的 `backtest.metrics` 下新增/使用：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `risk_free_rate` | float | 0.0 | 年化无风险利率（如 0.02 表示 2%），夏普与空仓计息共用。 |
| `accrue_risk_free_when_flat` | bool | true | 是否在空仓日对权益按无风险利率日复利；false 则空仓收益为 0（与旧逻辑一致）。 |

示例（启用空仓计息，年化 2%）：

```yaml
backtest:
  metrics:
    risk_free_rate: 0.02
    accrue_risk_free_when_flat: true
```

当 `risk_free_rate: 0.0` 时，即使用 `accrue_risk_free_when_flat: true`，日化利率为 0，权益不变，行为与“不计息”等价。

---

## 四、实现要点（runner.py）

1. **读取配置**  
   - `metrics.risk_free_rate`、`metrics.accrue_risk_free_when_flat`（默认 `True`）。  
   - 计算 `rfr_daily = (1 + risk_free_rate)^(1/252) - 1`，供每个 bar 使用。

2. **每 Bar 末尾**  
   - 在所有开平仓、止损止盈、熔断等逻辑之后，若 `position == 0` 且 `accrue_risk_free_when_flat`：  
     - `equity *= 1 + rfr_daily`  
     - 若 `equity > peak` 则更新 `peak`，并更新 `max_dd`。  
   - 随后照常计算本 bar 的 `bar_returns` 与 `prev_equity`。

3. **影响范围**  
   - **total_return**：因权益曲线包含空仓期利息而提高（在 `risk_free_rate > 0` 且空仓日较多时）。  
   - **max_drawdown**：基于含利息的权益曲线，与曲线一致。  
   - **sharpe_ratio**：分子仍为「年化收益 − risk_free_rate」，分母为含空仓日收益的日收益序列年化标准差，口径一致。  
   - **profit_factor / win_rate**：仅依赖已实现平仓的 PnL，与是否计息无关。

---

## 五、业界参考

- **现金无收益（0）**：不少回测框架默认空仓/现金收益为 0，便于只比较“交易本身”的收益。  
- **现金/无风险计息**：实务与部分框架会为未使用现金配置“cash yield”或“risk-free rate”，按日或按周期计息，使权益曲线更贴近真实账户。  
- **无风险利率选取**：常用 3 个月国债收益率或本国短期无风险利率作为年化 `risk_free_rate`，再按 252 日复利到日化。

本实现将“是否对空仓计息”做成可配置，既可与业界“现金计息”做法对齐，也可通过 `accrue_risk_free_when_flat: false` 保持原有 0 收益行为便于对比。

---

## 六、输出物与检查点

| 输出物 | 状态 |
|--------|------|
| 配置项 `accrue_risk_free_when_flat`、`risk_free_rate` 说明 | ✅ 第三节 |
| runner 空仓计息逻辑与 peak/max_dd 更新 | ✅ 第四节 |
| 本文档（v4 回测增强说明） | ✅ |
