# 开发步骤拆分（Development Task Breakdown）— v2

**文档版本**：v2  
**产出日期**：2026-02-09  
**依据**：研发流程步骤 5 - 开发步骤拆分  
**上游输入**：`docs/v2/04-technical-design.md`、`docs/v2/01-requirements_gathering.md`

---

## 1. 任务清单（v2 增量）

v2 在 **v1 已实现** 基础上做增量开发，以下任务按**依赖顺序**排列，估算采用 **Story Points（Fibonacci）**，优先级与 v2 需求一致（P0=Must, P1=Should, P2=Could）。

---

### T-v2-1. 回测与风控配置扩展

| 属性 | 内容 |
|------|------|
| **任务 ID** | T-v2-1 |
| **任务名称** | 回测与风控配置扩展 |
| **任务描述** | 在 `config/strategy.yaml` 下增加 `backtest` 段，或新增 `config/backtest.yaml`；包含：`use_stop_loss_take_profit`、`use_ma50_exit`、`circuit_breaker.enabled`/`drawdown_threshold`/`position_after`/`cooldown_bars`、`metrics.risk_free_rate`、`commission`。实现配置加载（与现有 config_loader 合并或单独 backtest 加载），回测入口能读取上述配置与默认值。（选择：新增 `config/backtest.yaml`） |
| **验收标准** | ① 配置结构符合 v2 TDD §2.4；② 回测 runner 可读取 use_stop_loss_take_profit、risk_free_rate 等；③ 未配置时使用合理默认（如 use_stop_loss_take_profit=true、risk_free_rate=0）；④ 不破坏现有 strategy 配置。 |
| **依赖** | 无（依赖 v1 现有 config 与 runner 入口） |
| **估算** | 2 SP |
| **优先级** | P0 |

---

### T-v2-2. 计算层：市场环境「连续 2 日」判定

| 属性 | 内容 |
|------|------|
| **任务 ID** | T-v2-2 |
| **任务名称** | 计算层：市场环境「连续 2 日」判定 |
| **任务描述** | 修改 `ndx_rsi/indicators/market_env.py` 中 `judge_market_env`：bull 需最近 2 日收盘均 ≥ 对应日 MA50 且斜率 > SLOPE_UP；bear 需最近 2 日收盘均 ≤ 对应日 MA50 且斜率 < SLOPE_DOWN；oscillate/transition 逻辑与 TDD 一致。保证 `len(prices)` 不足 2 或不足 SLOPE_LOOKBACK 时返回 "transition"。 |
| **验收标准** | ① 牛/熊判定使用连续 2 日与 MA50 比较；② 单测：至少 2 组输入（满足/不满足连续 2 日）得到预期 bull/bear/transition；③ 与 v1 单测或回测片段兼容（接口不变）。 |
| **依赖** | 无 |
| **估算** | 2 SP |
| **优先级** | P0 |

---

### T-v2-3. 回测引擎：Bar 内止损/止盈检查

| 属性 | 内容 |
|------|------|
| **任务 ID** | T-v2-3 |
| **任务名称** | 回测引擎：Bar 内止损/止盈检查 |
| **任务描述** | 在 `ndx_rsi/backtest/runner.py` 每 Bar 循环中，在应用信号开平仓**之前**：若当前有仓位，读取本 Bar 的 `risk["stop_loss"]`、`risk["take_profit"]`（来自 `strategy.calculate_risk(sig, window)`）；用当日 high/low 判断是否触达；多头：low<=stop_loss 或 high>=take_profit 则平多；空头：high>=stop_loss 或 low<=take_profit 则平空。触达则平仓、计入 PnL、更新 wins/losses 与 equity；同一 Bar 先检查止损再止盈。行为由配置 `use_stop_loss_take_profit` 控制（默认 true）。 |
| **验收标准** | ① 启用时，触达止损或止盈会平仓并记 PnL；② 平仓价可为 stop_loss/take_profit 或 close（与 TDD 约定一致）；③ 关闭配置时行为与 v1 一致（仅信号平仓）；④ 同一区间下「仅信号」与「信号+止损止盈」结果可对比。 |
| **依赖** | T-v2-1 |
| **估算** | 5 SP |
| **优先级** | P0 |

---

### T-v2-4. 回测引擎：可选趋势破位止损

| 属性 | 内容 |
|------|------|
| **任务 ID** | T-v2-4 |
| **任务名称** | 回测引擎：可选趋势破位止损 |
| **任务描述** | 在 Bar 内检查完止损/止盈后（若未因止损止盈平仓）：若配置 `use_ma50_exit` 为 true，多头且当日 close < ma50 则平多，空头且当日 close > ma50 则平空。平仓价用当日 close，PnL 计入并更新权益。可选：约定「有效跌破」为连续 2 日 close < MA50（与 v2 TDD 一致）。 |
| **验收标准** | ① 启用且满足条件时平仓；② 关闭时不影响现有逻辑；③ 与止损/止盈、信号平仓顺序正确，无重复平仓。 |
| **依赖** | T-v2-3 |
| **估算** | 2 SP |
| **优先级** | P1 |

---

### T-v2-5. 回测引擎：回撤熔断

| 属性 | 内容 |
|------|------|
| **任务 ID** | T-v2-5 |
| **任务名称** | 回测引擎：回撤熔断 |
| **任务描述** | 在回测循环中增加状态 `circuit_breaker_cooldown`；每 Bar 先更新权益与峰值，计算 dd=(peak-equity)/peak；若配置启用且 dd >= drawdown_threshold：若有仓位则平仓（或降仓至 position_after），并置 cooldown = cooldown_bars；若 cooldown > 0：本 Bar 禁止新开仓（仅允许平仓或观望），然后 cooldown -= 1。开仓分支中若 cooldown > 0 且信号为开仓，则忽略开仓。 |
| **验收标准** | ① 回撤达到阈值时触发平仓/降仓与 cooldown；② cooldown 期间不新开仓；③ 配置关闭时行为与无熔断一致；④ 可用历史区间或构造数据验证熔断触发。 |
| **依赖** | T-v2-1, T-v2-3 |
| **估算** | 3 SP |
| **优先级** | P1 |

---

### T-v2-6. 回测引擎：标准绩效指标

| 属性 | 内容 |
|------|------|
| **任务 ID** | T-v2-6 |
| **任务名称** | 回测引擎：标准绩效指标 |
| **任务描述** | 在回测过程中记录每笔平仓的 PnL 列表；汇总 gross_profit = sum(pnl for pnl in closed_pnls if pnl>0)，gross_loss = abs(sum(pnl for pnl in closed_pnls if pnl<0))；profit_factor = gross_profit / gross_loss（gross_loss==0 时置 99）。记录每 Bar 权益变化率 bar_returns；年化收益 = (1+total_return)^(252/bar_count)-1 或等价；年化波动率 = bar_returns.std() * sqrt(252)；sharpe_ratio = (ann_return - risk_free_rate) / ann_volatility；risk_free_rate 从配置读取。返回 dict 中 win_rate、total_trades、total_return、max_drawdown 保持，profit_factor 与 sharpe_ratio 改为上述标准定义。 |
| **验收标准** | ① profit_factor 与「总盈利/总亏损」一致；② 夏普使用收益序列标准差与配置的无风险利率；③ 同一回测多次运行指标稳定；④ 文档或注释标明公式与无风险利率来源。 |
| **依赖** | T-v2-1, T-v2-3 |
| **估算** | 3 SP |
| **优先级** | P0 |

---

### T-v2-7. 信号层：顶/底背离（可选）

| 属性 | 内容 |
|------|------|
| **任务 ID** | T-v2-7 |
| **任务名称** | 信号层：顶/底背离（可选） |
| **任务描述** | 实现 `check_divergence(prices, rsi, lookback, volume_ratio, require_volume)` 返回 "bearish_divergence"|"bullish_divergence"|None；顶背离=价格创新高且 RSI 未创新高，底背离=价格创新低且 RSI 未创新低；可选量能条件。在 `generate_signal_dict` 中若配置 `use_divergence: true` 则调用并接入组合（过滤或独立信号）。策略/信号配置中增加 use_divergence 开关。 |
| **验收标准** | ① 高低点识别与背离判定符合 design.md/PRD；② 可配置关闭，关闭时行为与 v1 一致；③ 单测至少 2 组价格+RSI 序列得到预期背离类型或 None。 |
| **依赖** | 无（与现有信号层并行） |
| **估算** | 5 SP |
| **优先级** | P2 |

---

### T-v2-8. 集成与回归验证

| 属性 | 内容 |
|------|------|
| **任务 ID** | T-v2-8 |
| **任务名称** | 集成与回归验证 |
| **任务描述** | 使用同一区间（如 2018-01-01～2025-12-31、QQQ）运行回测：① 关闭止损止盈与熔断，对比 v1 结果（至少 total_trades、win_rate 等可对比）；② 开启止损止盈、标准指标，产出新报表，验证 profit_factor、sharpe 公式正确；③ 可选开启回撤熔断，验证触发与 cooldown；④ 市场环境改为连续 2 日后，对比环境标签与信号数量变化。补充或更新 README/文档说明 v2 配置项与指标口径。 |
| **验收标准** | ① 回测可重复、指标口径符合 v2 需求；② 文档说明如何切换「仅信号」与「信号+止损止盈」；③ 无回归：v1 已有 CLI 命令仍可用。 |
| **依赖** | T-v2-2, T-v2-3, T-v2-5, T-v2-6（T-v2-4、T-v2-7 可选） |
| **估算** | 3 SP |
| **优先级** | P0 |

---

## 2. 任务依赖图（v2）

```
         T-v2-1 配置扩展
              |
     +--------+--------+
     |                 |
     v                 v
T-v2-2 连续2日    T-v2-3 止损止盈
     |                 |
     |                 +---> T-v2-4 趋势破位（可选）
     |                 |
     |                 +---> T-v2-5 回撤熔断
     |                 |
     |                 +---> T-v2-6 标准绩效
     |                 |
     +--------+--------+
              |
              v
         T-v2-8 集成与回归

T-v2-7 背离（可选，独立）
```

**关键路径**：T-v2-1 → T-v2-3 → T-v2-6 → T-v2-8；T-v2-2 可与 T-v2-3 并行。

---

## 3. 开发计划（v2 阶段）

| 阶段 | 任务 | 目标 |
|------|------|------|
| **Phase v2-1：配置与计算层** | T-v2-1, T-v2-2 | 回测配置可读、市场环境连续 2 日生效 |
| **Phase v2-2：回测引擎核心** | T-v2-3, T-v2-6 | Bar 内止损/止盈、标准 profit_factor 与夏普 |
| **Phase v2-3：回测增强与集成** | T-v2-4, T-v2-5, T-v2-8 | 可选趋势破位、回撤熔断、集成回归 |
| **Phase v2-4：可选** | T-v2-7 | 顶/底背离接入与配置开关 |

**建议顺序**：Phase v2-1 完成后做 Phase v2-2；Phase v2-2 完成后做 Phase v2-3；T-v2-7 可在 Phase v2-3 之后或并行。

---

## 4. 里程碑（v2）

| 里程碑 | 完成条件 |
|--------|----------|
| **M-v2-1** | T-v2-1、T-v2-2 完成；配置可读、judge_market_env 连续 2 日有单测与回测片段验证。 |
| **M-v2-2** | T-v2-3、T-v2-6 完成；回测启用止损/止盈且报表为标准 profit_factor、sharpe；同一区间可对比「仅信号」与「信号+止损止盈」。 |
| **M-v2-3** | T-v2-4、T-v2-5、T-v2-8 完成；可选趋势破位与回撤熔断可用；集成回归通过；文档更新。 |
| **M-v2-4（可选）** | T-v2-7 完成；背离可配置启用并在回测中对比。 |

---

## 5. 工作量汇总（v2）

| 优先级 | 任务 | Story Points |
|--------|------|---------------|
| P0 | T-v2-1, T-v2-2, T-v2-3, T-v2-6, T-v2-8 | 15 SP |
| P1 | T-v2-4, T-v2-5 | 5 SP |
| P2 | T-v2-7 | 5 SP |

**说明**：v2 仅增量开发，依赖 v1 已完成的 T1–T12；P0 完成后即可交付 v2 核心（止损止盈 + 连续 2 日 + 标准指标）。

---

## 6. 与 v2 需求对应

| 需求 ID | 任务 |
|---------|------|
| FR-v2-01 回测 Bar 内止损/止盈 | T-v2-3 |
| FR-v2-02 趋势破位止损 | T-v2-4 |
| FR-v2-03 市场环境连续 2 日 | T-v2-2 |
| FR-v2-04 标准绩效指标 | T-v2-6 |
| FR-v2-05 回撤熔断 | T-v2-5 |
| FR-v2-06 顶/底背离可选 | T-v2-7 |
| NFR-v2-01 可重复性 | T-v2-6, T-v2-8 |
| NFR-v2-02 指标口径 | T-v2-6 |
| NFR-v2-03 市场环境可测 | T-v2-2 |

---

## 7. 输出物清单

| 输出物 | 状态 |
|--------|------|
| v2 任务清单（Task List） | ✅ 第 1 节 |
| 任务依赖图（Dependency Graph） | ✅ 第 2 节 |
| 开发计划（Development Plan） | ✅ 第 3 节 |
| 里程碑（Milestone） | ✅ 第 4 节 |
| 与 v2 需求追溯 | ✅ 第 6 节 |

---

**下一步**：确认 v2 任务拆分与优先级后，进入「步骤 6：代码开发」。建议从 **T-v2-1（配置扩展）** 与 **T-v2-2（连续 2 日）** 开始，再实施 **T-v2-3（止损止盈）** 与 **T-v2-6（标准绩效）**。
