# V8 BRD「50日均线+成交量+RSI」策略 — 集成可行性评估

基于 [command-01-requirements-gathering](.cursor/skills/development_workflow/commands/command-01-requirements-gathering.md) 的要点，对 [brd.md](./brd.md) 能否转换为新策略并集成到 `index_data_analysis` 项目做了一次对照评估。

---

## 结论：**可以集成**

BRD 中的「趋势→动能→点位」三合一逻辑与伪代码均可落地为**一个新策略类**，复用项目现有指标与数据管道，仅在**趋势判定细节**和**信号规则**上按 BRD 单独实现即可。

---

## 一、BRD 与现有项目能力对照

| BRD 要求 | 项目现状 | 结论 |
|----------|----------|------|
| **50 日均线（SMA50）** | `calculate_ma(close, 50)` → `ma50` | ✅ 已有 |
| **无连续 2 日收盘跌破/站上 MA50** | `market_env.judge_market_env` 中已有 both_above / both_below | ✅ 一致 |
| **MA50 连续 3 日向上/下** | 当前用 20 日斜率拟合，非「连续 3 日」 | ⚠️ 需在新策略内按 BRD 实现 |
| **震荡：MA50 斜率 5 日 &lt;0.1% + 价格在 ±3%** | 现有 oscillate 为 20 日斜率 ±0.005 + ±3% | ⚠️ 新策略内按 BRD（5 日、0.1%）实现 |
| **20 日均量、vol_ratio** | `calculate_volume_ratio(volume, 20)` | ✅ 已有 |
| **放量 ≥1.2 / 缩量 ≤0.8** | `signal.trend_volume.get_volume_type` 一致 | ✅ 已有 |
| **RSI 14 日核心、9/24 辅助** | 现有 `rsi_9`、`rsi_24`，无 `rsi_14` | ⚠️ 新策略需增加 `rsi_14` 或配置 period=14 |
| **分趋势的 RSI+量能规则表** | `signal.combine` 有类似逻辑，但阈值/分支不全按 BRD | ⚠️ 新策略按 BRD 第四步表格实现 |

---

## 二、建议集成方式

1. **新增一个独立策略**（策略名已确定为 **`NDX_MA50_Volume_RSI`**；趋势与信号规则完全按 BRD 执行）
   - 继承 `BaseTradingStrategy`，实现 `generate_signal`、`calculate_risk`。
   - 趋势判定严格按 BRD 伪代码「第三步」：
     - 上升：收盘 &gt; SMA50 且 SMA50 连续 3 日向上，且无连续 2 日收盘跌破。
     - 下降：收盘 &lt; SMA50 且 SMA50 连续 3 日向下，且无连续 2 日站上。
     - 震荡：SMA50 连续 5 日斜率绝对值 &lt;0.1%，且收盘在 SMA50±3%。
   - 信号逻辑严格按 BRD「第四步」：按趋势类型 + RSI 区间 + vol_ratio（放量/缩量）输出操作建议（加仓/减仓/观望等），并映射为 `signal`/`position`。

2. **指标与数据**
   - 复用：`ma50`（SMA50）、`volume_ratio`（20 日均量比）。
   - 新增或配置：RSI 周期 14 作为主 RSI（可沿用 `calculate_rsi_handwrite(close, 14)`），如需与现有报告一致可同时保留 9/24。

3. **配置与注册**
   - 在 `config/strategy.yaml` 增加 **`NDX_MA50_Volume_RSI`** 段，参数可包括：`index_code`、`rsi_period`（默认 14）、`vol_ratio_heavy`（1.2）、`vol_ratio_light`（0.8）、`risk_control` 等。
   - 在 `ndx_rsi.strategy.factory` 中注册新策略名 → 新策略类。
   - 在 `cli_main.cmd_run_signal` 与 `backtest.runner` 中，对新策略名分支里确保计算并传入 `ma50`、`volume_ratio`、`rsi_14`（及可选 rsi_9/rsi_24），与现有 NDX_short / EMA 策略的指标准备方式一致。

4. **风控与报告**
   - `calculate_risk` 可沿用现有 `risk_control`（如止损/止盈比例），与 BRD 中的「止损 MA50 下方 2%」等描述对齐。
   - 若有统一 signal 报告（如 `format_signal_report`），可扩展对新策略的 `reason`/操作建议的展示。

---

## 三、需求梳理检查（对应 command-01）

| 检查项 | 说明 |
|--------|------|
| 核心功能与边界 | BRD 已明确：仅多空/轻仓建议、不涉及实盘下单；边界为 NDX/纳指、日频、50 日+20 日+RSI 周期。 |
| 利益相关者 | 使用方：量化/个人复盘；无额外角色。 |
| 功能/非功能 | 功能：趋势分类、RSI+量能信号、操作建议；非功能：可维护（单策略类+配置）、可回测（复用现有 backtest）。 |
| 风险与约束 | 历史规则基于 2018–2025 纳指；新市场或周期需重新验证；约束为现有数据源（如 yfinance）与 1d 数据。 |
| 需求确认 | 建议与产品/业务确认：是否接受「连续 3 日 MA50」「5 日斜率 0.1%」等严格量化定义，以及是否需支持背离等进阶规则（BRD 有描述，可做二期）。 |

---

## 四、建议的下一步（已确认）

- **策略名**：**NDX_MA50_Volume_RSI**
- **趋势与信号规则**：完全按 BRD 执行（含阈值 1.2/0.8、连续 3 日/5 日等）。
- 后续：进入步骤 2「需求文档」→ 技术方案与开发；实现顺序为先「趋势判定 + RSI+量能」核心信号与 `generate_signal`，再接 `calculate_risk`、配置、factory 与 CLI/回测分支；报告与背离可后续迭代。

---

*本评估基于当前 `index_data_analysis` 代码结构与 BRD v8 内容，可直接作为是否将 BRD 转为新策略集成的决策依据。*
