# 技术方案设计文档（Technical Design Document, TDD）— v2

**文档版本**：v2  
**产出日期**：2026-02-09  
**依据**：研发流程步骤 4 - 技术方案设计；v2 需求梳理 `01-requirements_gathering.md`  
**上游输入**：`docs/v1/04-technical-design.md`（沿用架构）、`docs/v1/07-simplifications-and-backtest-impact.md`

---

## 1. v2 架构与变更范围

### 1.1 与 v1 的关系

v2 **不改变** v1 的整体分层与入口，仅在以下模块做**增强或修正**：

| 层级 | v1 状态 | v2 变更 |
|------|----------|---------|
| 入口层（CLI） | 不变 | 回测命令可选增加 `--use-sl-tp`、`--use-circuit-breaker` 等开关（或统一由配置控制） |
| 回测层 | 自研循环，仅信号平仓 | **增强**：Bar 内止损/止盈检查、可选趋势破位、回撤熔断、标准绩效计算 |
| 计算层（市场环境） | judge_market_env 用「最近一根」 | **修正**：改为「连续 2 日」与 MA50 关系 |
| 信号层 | 无背离 | **可选**：顶/底背离识别并接入组合 |
| 策略层 / 风控层 | 已输出 stop_loss、take_profit | 不变；回测层**使用**这些输出 |
| 配置层 | strategy.yaml 含 risk_control | **扩展**：回测专用配置（止损止盈开关、熔断参数、无风险利率等） |

### 1.2 v2 变更架构示意

```
                    ┌─────────────────────────────────────────────────────────┐
                    │                    回测层（v2 增强）                      │
                    │  每 Bar：信号 → 风控 stop_loss/take_profit               │
                    │         → 先检查止损/止盈/趋势破位触达 → 再检查信号换向    │
                    │         → 回撤熔断状态机 → 权益与绩效统计                 │
                    │  输出：win_rate, profit_factor(标准), max_drawdown,       │
                    │        total_return, sharpe_ratio(标准), total_trades     │
                    └─────────────────────────────────────────────────────────┘
                                         │
    计算层（v2 修正）                     │
    judge_market_env：连续 2 日与 MA50   │
    ─────────────────────────────────────┘
```

---

## 2. 模块变更与接口规范

### 2.1 计算层：市场环境判定（v2 修正）

**文件**：`ndx_rsi/indicators/market_env.py`

**变更**：`judge_market_env(prices, ma50)` 中，牛/熊判定由「最近 1 日收盘与 MA50」改为「**连续 2 日**收盘价与 MA50 关系」。

**规则（与 v1 TDD / design.md 一致）**：

- **bull**：MA50 斜率 > `SLOPE_UP`（如 0.001），且**最近 2 日**收盘价均 ≥ 对应日 MA50（或均在 MA50 上方）。
- **bear**：MA50 斜率 < `SLOPE_DOWN`（如 -0.001），且**最近 2 日**收盘价均 ≤ 对应日 MA50。
- **oscillate**：斜率在 `SLOPE_FLAT_LOW`～`SLOPE_FLAT_HIGH` 且最近价格在 MA50±3% 内（可保留「最近 2 日」或沿用当前逻辑，以与设计文档一致为准）。
- **transition**：以上均不满足。

**接口**：签名不变，仍为 `judge_market_env(prices: pd.Series, ma50: pd.Series) -> str`。

**实现要点**：

- 取 `prices.iloc[-2:]` 与 `ma50.iloc[-2:]`，逐日比较收盘与当日 MA50。
- 若 `len(prices) < SLOPE_LOOKBACK` 或不足 2 根，返回 `"transition"`。

---

### 2.2 回测层：Bar 内止损/止盈与趋势破位（v2 增强）

**文件**：`ndx_rsi/backtest/runner.py`（或拆分为 `runner_core` + 配置读取）。

#### 2.2.1 每 Bar 执行顺序（建议）

在现有「按日推进、先取信号与风控」基础上，**在应用信号改变仓位之前**，对**当前已有仓位**做以下检查（顺序固定，先触达先平仓）：

1. **止损/止盈（可选，由配置开启）**  
   - 多头：若当根 K 线 `low <= stop_loss` → 以 stop_loss 价平多（或以 low 触达近似）；若 `high >= take_profit` → 以 take_profit 价平多。  
   - 空头：若当根 K 线 `high >= stop_loss` → 平空；若 `low <= take_profit` → 平空。  
   - 同一 Bar 若止损与止盈均可触达，需约定优先级（建议：**先检查止损再止盈**，或按触达顺序；文档与实现一致即可）。

2. **趋势破位止损（可选，由配置开启）**  
   - 多头：若当日收盘价 < MA50（且可约定「有效跌破」为连续 2 日收盘 < MA50），则平多。  
   - 空头：若当日收盘价 > MA50，则平空。  
   - 可与「信号平仓」共用同一平仓逻辑，仅触发条件不同。

3. **信号驱动开平仓（现有逻辑）**  
   - 若未因 1/2 平仓，再按 `sig["position"]` 与当前 `position` 判断是否平仓、开仓或换向；平仓时 PnL 按当前 Bar 的 close 或约定价格计算。

**止损/止盈数据来源**：每 Bar 调用 `strategy.calculate_risk(sig, window)`，从返回的 `risk["stop_loss"]`、`risk["take_profit"]` 读取；若当前无仓位则跳过 1。

#### 2.2.2 回撤熔断（可选，由配置开启）

- **状态**：增加回测状态 `circuit_breaker_cooldown: int`（剩余暂停开仓的天数，0 表示未熔断）。
- **每 Bar 更新**：  
  - 先更新权益与峰值，计算当前回撤 `dd = (peak - equity) / peak`。  
  - 若 `dd >= circuit_breaker_threshold`（如 0.10）：  
    - 若有仓位，强制平仓（或降仓至约定比例，如 30%，具体以 PRD 为准）；  
    - 置 `circuit_breaker_cooldown = N`（如 2）。  
  - 若 `circuit_breaker_cooldown > 0`：本 Bar 不允许新开仓（仅允许平仓或观望），然后 `circuit_breaker_cooldown -= 1`。
- **开仓判断**：在「信号驱动开平仓」分支中，若 `circuit_breaker_cooldown > 0` 且动作为开仓，则忽略开仓、保持观望。

#### 2.2.3 绩效指标（v2 标准定义）

- **总盈利 / 总亏损**：按每笔已平仓交易的 PnL 汇总，`gross_profit = sum(pnl for pnl in closed_pnls if pnl > 0)`，`gross_loss = abs(sum(pnl for pnl in closed_pnls if pnl < 0))`。
- **profit_factor**：`gross_profit / gross_loss`；若 `gross_loss == 0`，则置为 `99` 或单独标注（与 v2 需求约定一致）。
- **夏普比率**：  
  - 按**日收益序列**（或 Bar 收益序列）计算：每 Bar 权益变化率为 `returns`。  
  - 年化收益：`ann_return = (1 + total_return)^(252/bar_count) - 1` 或等价的年化方式。  
  - 年化波动率：`returns.std() * sqrt(252)`（日线）或按实际 Bar 数折算。  
  - `sharpe_ratio = (ann_return - risk_free_rate) / ann_volatility`；无风险利率由配置传入（如 0 或 0.02）。
- **盈亏比（可选补充）**：`avg_win / avg_loss`，其中 `avg_win`、`avg_loss` 为盈利交易与亏损交易的平均盈亏金额（不含手续费可单独说明）。

**回测输出**：保持 `win_rate, total_trades, total_return, max_drawdown, sharpe_ratio, profit_factor`；v2 中 `profit_factor` 与 `sharpe_ratio` 必须按上述定义计算。

---

### 2.3 信号层：顶/底背离（v2 可选）

**文件**：`ndx_rsi/signal/rsi_signals.py`（或新建 `rsi_divergence.py`），由 `combine.py` 在配置开启时调用。

**职责**：在给定窗口内识别价格与 RSI 的高低点，判断顶背离/底背离，并可选结合量能条件。

- **顶背离**：价格创新高（近期高点比前一次高点高），RSI 未创新高（近期 RSI 高点 ≤ 前一次 RSI 高点）。  
- **底背离**：价格创新低，RSI 未创新低。

**接口建议**：

```python
def check_divergence(
    prices: pd.Series,
    rsi: pd.Series,
    lookback: int = 20,
    volume_ratio: Optional[float] = None,
    require_volume: bool = True,
) -> Optional[str]:
    """
    返回 "bearish_divergence" | "bullish_divergence" | None。
    require_volume 为 True 时，可要求放量/缩量等条件与 design.md 一致。
    """
```

**接入组合**：在 `generate_signal_dict` 中，若配置 `use_divergence: true`，则先或与金叉/死叉、超买超卖一起判断；背离可作为过滤（例如有顶背离时弱化买入）或独立信号（如底背离 + 量能 → 买入）。具体优先级与 v1 信号组合规则一致（趋势 > 量能 > RSI）。

---

### 2.4 配置层：回测与风控扩展（v2）

**方式一**：在 `config/strategy.yaml` 下为 NDX_short_term（或全局）增加 `backtest` 段。

**方式二**：单独 `config/backtest.yaml`，由回测入口加载，与 strategy 配置合并或覆盖。

建议结构（YAML 示例）：

```yaml
# config/backtest.yaml 或 strategy.yaml 内 backtest 段
backtest:
  use_stop_loss_take_profit: true   # 是否在 Bar 内检查止损/止盈
  use_ma50_exit: false              # 是否启用趋势破位（收盘跌破/站上 MA50）平仓
  circuit_breaker:
    enabled: false
    drawdown_threshold: 0.10        # 回撤达到 10% 触发
    position_after: 0.30            # 熔断后允许的最大仓位比例（或平仓后仅允许该比例开仓）
    cooldown_bars: 2                # 暂停开仓的 Bar 数
  metrics:
    risk_free_rate: 0.0            # 夏普计算用无风险利率
  commission: 0.0005
```

策略层已有 `risk_control.stop_loss_ratio`、`take_profit_ratio`，回测层直接读取；若回测需要单独开关，可在 `backtest` 下增加 `use_stop_loss_take_profit` 等。

---

## 3. 回测引擎 v2 流程（单 Bar 伪代码）

```
for each bar i (from warmup to end):
    window = df.iloc[:i+1]
    row = bar i (open, high, low, close, volume, ma50, ...)
    sig = strategy.generate_signal(window)
    risk = strategy.calculate_risk(sig, window)

    # ------ 1. 回撤熔断状态更新（若启用）------
    equity, peak = update_equity(equity, position, entries, row)
    if circuit_breaker.enabled:
        dd = (peak - equity) / peak
        if dd >= circuit_breaker.drawdown_threshold:
            position = reduce_or_flatten(position, circuit_breaker.position_after)
            circuit_breaker_cooldown = circuit_breaker.cooldown_bars
        if circuit_breaker_cooldown > 0:
            allow_new_position = False
            circuit_breaker_cooldown -= 1
        else:
            allow_new_position = True

    # ------ 2. 若当前有仓位：检查止损/止盈/趋势破位 ------
    if position != 0 and use_stop_loss_take_profit:
        sl, tp = risk["stop_loss"], risk["take_profit"]
        if long and (row.low <= sl or row.high >= tp):  # 触达则平仓，记 PnL
            close_position(sl or tp); record_pnl(); position = 0; entries.clear()
        elif short and (row.high >= sl or row.low <= tp):
            close_position(sl or tp); record_pnl(); position = 0; entries.clear()
    if position != 0 and use_ma50_exit:
        if long and row.close < row.ma50: close_position(row.close); ...
        if short and row.close > row.ma50: close_position(row.close); ...

    # ------ 3. 信号驱动开平仓（与 v1 一致，但受 allow_new_position 约束）------
    pos_new = sig["position"] if allow_new_position else (0.0 if position != 0 else 0.0)  # 熔断期间禁止新开
    if pos_new != 0 and position == 0:  # 开仓
        position = pos_new; entries.append(...)
    elif (pos_new == 0 or sign(pos_new) != sign(position)) and position != 0:  # 平仓或换向
        close_position(row.close); record_pnl(); then if pos_new != 0: open_position(...)

    # ------ 4. 记录日收益（用于夏普）------
    bar_returns.append((equity - prev_equity) / prev_equity)
```

最后汇总：`gross_profit`、`gross_loss` → `profit_factor`；`bar_returns` → 年化收益与标准差 → `sharpe_ratio`。

---

## 4. 数据流与时序（v2 回测）

与 v1 相比，回测层内部多出「每 Bar 先风控检查、再信号执行」的步骤，且绩效统计改为标准公式。

```
用户/CLI               策略层              回测引擎（v2）
   |                     |                        |
   | run_backtest        |                        |
   |-------------------->|                        |
   |                     |  get_historical        |
   |                     |  preprocess + indicators|
   |                     |  (含 judge_market_env 连续2日) |
   |                     |                        |
   |                     |  对每个 Bar i:         |
   |                     |  generate_signal(window)|
   |                     |  calculate_risk(sig, window) |
   |                     |------------------------>|
   |                     |                        | 检查熔断状态
   |                     |                        | 检查止损/止盈/MA50 破位
   |                     |                        | 若触达则平仓、记 PnL
   |                     |                        | 再按信号开平仓（受熔断约束）
   |                     |                        | 更新权益、峰值、bar_returns
   |                     |                        |
   |                     |                        | 汇总：gross_profit/loss → profit_factor
   |                     |                        | bar_returns → sharpe_ratio
   |<-----------------------------------------------------|
   |  返回绩效 dict（标准口径）                           |
```

---

## 5. 与 v2 需求对应

| 需求 ID | 本设计对应 |
|---------|------------|
| FR-v2-01 回测 Bar 内止损/止盈 | §2.2.1 每 Bar 执行顺序、§3 伪代码 |
| FR-v2-02 趋势破位止损 | §2.2.1、配置 `use_ma50_exit` |
| FR-v2-03 市场环境连续 2 日 | §2.1 judge_market_env |
| FR-v2-04 标准绩效指标 | §2.2.3 profit_factor、夏普、可选盈亏比 |
| FR-v2-05 回撤熔断 | §2.2.2、§2.4 配置 circuit_breaker |
| FR-v2-06 顶/底背离可选 | §2.3 信号层背离、配置 use_divergence |
| FR-v2-07 VIX 可选 | 风控层已有 check_extreme_market；若数据源提供 VIX 可传入，本 TDD 不扩展 |
| NFR-v2-01 可重复性 | 固定随机种子无；逻辑确定性保证同一输入同一输出 |
| NFR-v2-02 指标口径 | §2.2.3 |
| NFR-v2-03 市场环境可测 | §2.1 单测或回测片段验证连续 2 日 |

---

## 6. 技术风险与缓解（v2）

| 风险 | 缓解 |
|------|------|
| 止损/止盈在同一 Bar 与信号换向逻辑重叠 | 明确顺序：先止损止盈平仓，再信号开平仓；同一 Bar 至多一次「风控平仓」或「信号平仓」 |
| 回撤熔断与权益更新顺序不当导致指标失真 | 先更新权益再算回撤，再判断熔断；熔断后的平仓在下一 Bar 或本 Bar 立即反映到权益 |
| 日收益序列长度不足导致夏普不稳定 | 回测区间至少数月；若 Bar 数过少，夏普可标注为 None 或 N/A |
| 背离实现增加复杂度与 bug | 背离为可选、可配置关闭；单测覆盖高低点识别与边界条件 |

---

## 7. 输出物清单（v2）

| 输出物 | 状态 |
|--------|------|
| v2 技术设计文档（本文档） | ✅ |
| 回测层增强规范（Bar 内检查、熔断、绩效） | ✅ §2.2、§3 |
| 计算层 market_env 修正规范 | ✅ §2.1 |
| 信号层背离可选规范 | ✅ §2.3 |
| 回测/风控配置扩展 | ✅ §2.4 |
| 与 v2 需求追溯 | ✅ §5 |

---

**下一步**：进入 v2 开发任务拆分（05-development-task-breakdown），按 P0 → P1 → P2 分步实现并验收。
