# v2 代码开发与验收

**文档版本**：v2  
**产出日期**：2026-02-09  
**依据**：`05-development-task-breakdown.md` 与 `04-technical-design.md`

---

## 1. 实现摘要

| 任务 | 状态 | 实现位置 |
|------|------|----------|
| T-v2-1 回测与风控配置扩展 | ✅ | `config/strategy.yaml` 增加 `backtest` 段；`ndx_rsi/config_loader.py` 增加 `get_backtest_config()` |
| T-v2-2 市场环境连续 2 日判定 | ✅ | `ndx_rsi/indicators/market_env.py` 中 `judge_market_env` 改为最近 2 日收盘与 MA50 比较 |
| T-v2-3 Bar 内止损/止盈 | ✅ | `ndx_rsi/backtest/runner.py` 每 Bar 用开仓时保存的 sl/tp 检查 high/low 触达并平仓 |
| T-v2-4 可选趋势破位止损 | ✅ | `runner.py` 中 `use_ma50_exit` 为 true 时收盘价跌破/站上 MA50 平仓 |
| T-v2-5 回撤熔断 | ✅ | `runner.py` 中 `circuit_breaker.enabled` 为 true 时回撤≥阈值平仓并 cooldown 禁止新开仓 |
| T-v2-6 标准绩效指标 | ✅ | `runner.py` 中 profit_factor = 总盈利/总亏损，夏普 = (年化收益 - 无风险)/收益标准差 |
| T-v2-7 顶/底背离（可选） | ✅ | `ndx_rsi/signal/rsi_signals.py` 增加 `check_divergence`；`combine.py` 与策略配置 `use_divergence` 接入 |
| T-v2-8 集成与回归 | ✅ | 见下文运行与对比说明 |

---

## 2. 配置说明（v2）

### 2.1 回测配置（config/strategy.yaml 顶层 `backtest`）

```yaml
backtest:
  use_stop_loss_take_profit: true   # Bar 内检查止损/止盈
  use_ma50_exit: false              # 趋势破位（收盘跌破/站上 MA50）平仓
  circuit_breaker:
    enabled: false
    drawdown_threshold: 0.10
    position_after: 0.30
    cooldown_bars: 2
  metrics:
    risk_free_rate: 0.0              # 夏普计算用无风险利率
  commission: 0.0005
```

### 2.2 策略配置中的 v2 项（NDX_short_term）

- `use_divergence: false`：设为 `true` 可启用顶/底背离信号。
- `divergence_lookback: 20`：背离识别回溯 K 线数（可选，默认 20）。

---

## 3. 运行与验收

### 3.1 回测命令（与 v1 相同）

```bash
python -m ndx_rsi.cli_main run_backtest --strategy NDX_short_term --symbol QQQ --start 2018-01-01 --end 2025-12-31
```

### 3.2 指标口径（v2）

- **profit_factor**：总盈利 / 总亏损（总亏损为 0 时返回 99）。
- **sharpe_ratio**：(年化收益 - risk_free_rate) / 年化收益标准差，年化收益由 `(1+total_return)^(1/years)-1` 得到，收益序列为每 Bar 权益变化率。

### 3.3 对比「仅信号平仓」与「信号 + 止损止盈」

- 将 `backtest.use_stop_loss_take_profit` 设为 `false` 可近似 v1 行为（仅信号平仓）；设为 `true` 为 v2 默认（Bar 内止损/止盈）。
- 同一区间下可对比 total_trades、win_rate、total_return、max_drawdown、profit_factor、sharpe_ratio。

### 3.4 回归

- v1 已有命令 `run_backtest`、`run_signal`、`verify_indicators` 均可用；回测多次运行结果稳定（相同配置下指标一致）。

---

## 4. 验收检查点

1. ✅ 回测配置可从 `get_backtest_config()` 读取且默认值符合 TDD。
2. ✅ `judge_market_env` 牛/熊使用连续 2 日与 MA50 关系。
3. ✅ 启用止损/止盈时触达 sl/tp 会平仓；开仓时保存的 sl/tp 用于后续 Bar 检查。
4. ✅ 启用趋势破位时收盘价与 MA50 关系触发平仓。
5. ✅ 启用回撤熔断时回撤≥阈值平仓并进入 cooldown。
6. ✅ profit_factor、sharpe 按标准定义计算。
7. ✅ `use_divergence: true` 时背离信号可触发买卖；默认 false 时行为与 v1 一致。
8. ✅ 同一策略/标的/区间/配置多次回测结果一致。

---

**下一步**：可根据需要补充单测（如 `judge_market_env` 连续 2 日、`check_divergence` 边界用例）、或扩展 README 中 v2 配置与运行说明。
