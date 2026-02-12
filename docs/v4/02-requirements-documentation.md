# 需求规格说明书（SRS / PRD）— v4 EMA 策略与回测可视化集成

**文档编号**：SRS-NDX-RSI-v4  
**文档版本**：1.0  
**产出日期**：2026-02-12  
**依据**：研发流程步骤 2 - 需求文档  
**参考规范**：IEEE 830-1998、ISO/IEC/IEEE 29148、FURPS+、需求可追溯性矩阵（RTM）  
**上游输入**：nasdaq_v1 项目（策略、回测、可视化）、index_data_analysis 现有架构与 CLI  
**变更性质**：在 index_data_analysis 中新增 EMA 策略族（v1 交叉 / v2 趋势增强），并统一回测后可视化能力

---

## 1. 项目概述

### 1.1 背景

index_data_analysis 当前已具备 NDX RSI 短线策略（50 日均线定趋势 + 成交量 + RSI）、统一回测引擎与 CLI，但**仅支持单一策略族**，且回测结果仅输出汇总指标（win_rate、total_return、max_drawdown 等），**无按日收益序列与可视化**。nasdaq_v1 项目实现了基于 EMA 的两种策略（v1：50/200 日 EMA 交叉 + 5% 止损；v2：80/200 日 EMA 趋势 + 波动率过滤）及完整的回测与 matplotlib 可视化。为复用成熟策略逻辑并提升分析体验，需将上述能力集成到 index_data_analysis 中，形成多策略、可对比、可可视化的统一平台。

### 1.2 目标

- 在 index_data_analysis 中**新增 EMA 策略族**：实现与 nasdaq_v1 逻辑一致的「EMA 交叉 v1」与「趋势增强 v2」策略，并接入现有回测与 CLI。
- **统一回测输出**：扩展回测引擎，在返回汇总指标的同时返回**按日序列**（权益、仓位、基准/策略累计收益等），供可视化与对比分析使用。
- **集成回测后可视化**：在 index_data_analysis 中提供累计收益曲线、策略对比图等可视化能力，使 NDX RSI 与 EMA 策略均可「回测 → 看图」。
- 保持现有 NDX RSI 策略与 CLI 行为不变，仅做增量扩展。

### 1.3 范围

| 维度 | 范围内 | 范围外 |
|------|--------|--------|
| 策略 | EMA 交叉 v1（50/200 EMA + 日线/月度调仓 + 5% 止损）、趋势增强 v2（80/200 EMA + 波动率过滤） | nasdaq_v1 的「每日趋势检测」独立脚本（可后续迭代） |
| 数据 | 复用现有 YFinance 数据源与预处理；为 EMA 策略预计算 ema_50/ema_200（v1）或 ema_80/ema_200、vol_20（v2） | 新数据源、新频率 |
| 回测 | 扩展 runner 返回按日序列；NDX RSI 与 EMA 策略共用同一套回测框架 | 修改现有回测核心逻辑（仅扩展输出） |
| 可视化 | 累计收益对比（策略 vs 基准）、可选 EMA+买卖点、多策略对比图 | 实时监控大屏、K 线组件 |
| 用户 | 策略/量化开发、回测分析 | 实盘下单、合规审批 |

---

## 2. 功能需求（详细描述）

以下功能需求按模块组织，并给出详细描述与验收标准。

---

### 2.1 EMA 策略实现与接入（FR-V4-01）

**描述**：在 index_data_analysis 中实现与 nasdaq_v1 逻辑一致的两种 EMA 策略，并接入现有策略工厂与配置。

**详细要求**：

- **策略接口**：新策略实现现有 `BaseTradingStrategy` 接口（`generate_signal(data, current_position_info=None)`、`calculate_risk(signal, data)`），与 NDX RSI 策略共用同一套回测驱动方式。
- **EMA 交叉 v1**：
  - 信号逻辑：黄金交叉（50 日 EMA 上穿 200 日 EMA）→ 买入（position=1）；死亡交叉（下穿）→ 卖出（position=0）。
  - 支持日线调仓与月度调仓两种模式（可通过配置或策略参数选择；月度模式下在每月最后一个交易日根据 EMA 趋势决定持仓）。
  - 止损：持仓期间若从最高点回撤达到 5%（可配置），平仓。
- **趋势增强 v2**：
  - 趋势：80 日 EMA > 200 日 EMA 视为上升趋势。
  - 波动率过滤：近 20 日收益率标准差（vol_20）低于配置阈值（如 2%）视为低波动。
  - 仅在「上升趋势 + 低波动」时满仓（position=1），其余空仓（position=0）。
- **数据依赖**：回测前由 runner 或数据层为 EMA 策略预计算并写入 DataFrame：v1 需 `close`、`ema_50`、`ema_200`；v2 需 `close`、`ema_80`、`ema_200`、`vol_20`（或等名字段）。指标计算方式与 nasdaq_v1 一致（EMA 为 ewm(span=..., adjust=False).mean()；波动率为日收益率 rolling(20).std()）。
- **配置**：在 `config/strategy.yaml` 中新增策略条目（如 `EMA_cross_v1`、`EMA_trend_v2`），参数包括均线周期、止损比例、波动率窗口与阈值等，与 nasdaq_v1 的 config 对齐。

**验收标准**：

- `run_backtest --strategy EMA_cross_v1` 与 `run_backtest --strategy EMA_trend_v2` 可正常运行，且输出汇总指标与 nasdaq_v1 同参数下的结果在合理误差范围内（如累计收益率差异 < 1%）。
- 策略仅依赖预计算好的 EMA/vol 列，不修改现有数据源接口。
- 配置项修改后重新回测生效。

---

### 2.2 回测引擎扩展：按日序列输出（FR-V4-02）

**描述**：扩展现有回测 runner，在返回汇总指标的同时，可选返回按日的时间序列数据，用于可视化和对比。

**详细要求**：

- **序列内容**：每个交易日至少包含：日期（index）、当日结束后权益（或累计收益倍数）、当日仓位、基准累计收益（buy & hold）、策略累计收益。可选：当日 signal/reason、EMA 等（便于画买卖点）。
- **接口**：例如 `run_backtest(..., return_series=True)` 返回 `(result_dict, series_df)`；`return_series=False`（默认）时保持现有行为仅返回 `result_dict`，保证向后兼容。
- **适用策略**：所有通过 `create_strategy` 创建的策略（含 NDX_short_term、EMA_cross_v1、EMA_trend_v2）在回测时均可产出 series_df；序列长度与回测区间一致（从首日到末日的每个交易日一行）。

**验收标准**：

- 现有调用 `run_backtest()` 不传 `return_series` 时行为与当前一致，仅返回 dict。
- 传 `return_series=True` 时得到 DataFrame，列至少包含 equity 或 strategy_cum_return、benchmark_cum_return、position，且与汇总指标中的 total_return、max_drawdown 等一致（可交叉验证）。
- 对 NDX_short_term 与 EMA_cross_v1 各跑一次，序列长度与回测区间一致。

---

### 2.3 回测后可视化模块（FR-V4-03）

**描述**：在 index_data_analysis 中新增可视化模块，基于回测产出的按日序列与（可选）原始 OHLCV+指标数据，绘制累计收益曲线及策略对比图。

**详细要求**：

- **累计收益对比图**：横轴为日期，纵轴为累计收益倍数（从 1 起）；至少绘制「基准（buy & hold）」与「当前策略」两条曲线；支持多策略同图对比（如 NDX RSI vs EMA v1 vs EMA v2）。
- **可选：EMA + 买卖点图**：针对 EMA 策略，绘制价格、EMA 均线及黄金/死亡交叉标记点；需要回测或数据层提供带 signal/position 的序列或原始数据。
- **输出方式**：支持弹窗显示（plt.show()）与保存到文件（如指定路径或默认 output/ 目录）；图片格式为 PNG，分辨率与图例清晰可读。
- **依赖**：使用 matplotlib，与 nasdaq_v1 的 plot 风格可对齐（字体、图例、网格等），实现可参考或移植 nasdaq_v1 的 `plot_cumulative_returns`、`plot_ema_signals`、`plot_compare_v1_v2` 等，但接口接受 index_data_analysis 的 series_df 与配置（如标的名称、策略名称）。

**验收标准**：

- 对任一回测结果（NDX_short_term 或 EMA 策略），调用可视化接口能生成「策略 vs 基准」累计收益图，且曲线与 series_df 数据一致。
- 对 EMA 策略能生成「价格 + EMA + 买卖点」图（若需求实现该图）。
- 保存到文件时路径正确、可打开且图例无遮挡。

---

### 2.4 CLI 与入口扩展（FR-V4-04）

**描述**：在现有 CLI 中支持选择 EMA 策略及触发回测后可视化，便于一键「回测 + 看图」；并支持 EMA 策略的**当前信号**生成。

**详细要求**：

- **策略选择**：`run_backtest` 子命令的 `--strategy` 参数支持新增值：`EMA_cross_v1`、`EMA_trend_v2`（及已有 `NDX_short_term`）。
- **可视化触发**：新增子命令（如 `plot_backtest`）或 `run_backtest` 的选项（如 `--plot` / `--save-plot`），在回测完成后根据返回的 series_df 调用可视化模块，展示或保存图表。
- **当前信号（run_signal）**：`run_signal` 子命令的 `--strategy` 同样支持 `EMA_cross_v1`、`EMA_trend_v2`。因 EMA 策略需 200+ 根 K 线（如 ema_200），拉取数据时对上述策略使用更长历史（如约 400 个自然日）以保证指标可算，再基于最新一根 K 线输出当前信号与风控参数。
- **参数透传**：标的、起止日期等与现有 `run_backtest` 一致，可视化时使用的标题或图例可包含策略名与标的。

**验收标准**：

- `python -m ndx_rsi.cli_main run_backtest --strategy EMA_cross_v1 --symbol QQQ --start 2003-01-01 --end 2025-12-31` 正常完成并输出汇总指标。
- 使用 `--plot` 或新子命令后，能弹出或保存累计收益图，且图中数据与本次回测一致。
- `python -m ndx_rsi.cli_main run_signal --strategy EMA_cross_v1 --symbol QQQ`（及 EMA_trend_v2）能正常输出 Signal 与 Risk，无「数据不足」报错。
- README 或帮助信息中补充新策略、可视化与 run_signal 用法说明。

---

## 3. 非功能需求

### 3.1 向后兼容（NFR-V4-01）

- 现有 `run_backtest()` 默认行为不变：不传 `return_series` 时仅返回 dict，不增加必须参数。
- 现有策略 `NDX_short_term` 与现有 CLI 子命令、配置文件结构保持可用，不破坏现有调用方。

### 3.2 可维护性与可扩展性（NFR-V4-02）

- EMA 策略与 NDX RSI 策略共用同一套数据接口、回测循环与可视化入口；新增其他策略时，仅需实现策略类并注册，即可复用回测与绘图。
- 可视化模块与策略逻辑解耦：绘图函数仅依赖「按日序列 DataFrame」与少量配置，不依赖具体策略类。

### 3.3 可测试性（NFR-V4-03）

- 新增 EMA 策略应有单元测试（如给定带 ema_50/ema_200 的 DataFrame，验证黄金/死亡交叉输出 position 正确）。
- 回测扩展：可对「固定输入序列 + 固定策略」断言返回的 series_df 关键列与汇总指标一致。
- 可视化模块可测：传入 mock series_df，校验不抛错且生成文件或返回 figure（不强制像素级比对）。

### 3.4 性能（NFR-V4-04）

- 预计算 EMA/vol 不应显著增加回测时间（相对现有仅 MA50/RSI 等，增加 < 10% 为可接受）。
- 绘图在回测结束后执行，不阻塞回测逻辑；大区间（如 20 年日线）下绘图在数秒内完成。

---

## 4. 约束条件

| 类型 | 约束内容 |
|------|----------|
| 架构 | 不改变现有分层架构；新策略放入 strategy/，可视化可独立模块（如 plot/ 或 viz.py）；回测 runner 仅扩展返回值，不重写核心循环。 |
| 数据 | 复用现有 YFinance 与 preprocess；EMA/vol 在回测前由 runner 或策略侧按需计算并写入 DataFrame。 |
| 依赖 | 可视化依赖 matplotlib；不强制引入新重型依赖。 |
| 范围 | 首版不实现 nasdaq_v1 的「每日趋势检测」独立脚本；可选在后续版本中以子命令形式接入。 |

---

## 5. 验收标准汇总

| 需求 ID | 验收标准摘要 |
|---------|--------------|
| FR-V4-01 | EMA_cross_v1 / EMA_trend_v2 实现并注册；回测结果与 nasdaq_v1 同参数下一致；配置化生效。 |
| FR-V4-02 | run_backtest(..., return_series=True) 返回 (dict, series_df)；序列含 equity/累计收益、position、基准；默认不传时行为不变。 |
| FR-V4-03 | 可视化模块能根据 series_df 绘制策略 vs 基准累计收益图；可选 EMA+买卖点图；支持显示与保存。 |
| FR-V4-04 | CLI 支持 --strategy EMA_cross_v1/EMA_trend_v2；run_backtest 回测后绘图（--plot/--save-plot）；run_signal 支持 EMA 策略并输出当前信号；文档更新。 |
| NFR-V4-01 | 现有 run_backtest 与 NDX_short_term 行为不变。 |
| NFR-V4-02 | 策略与绘图解耦，新增策略可复用回测与可视化。 |
| NFR-V4-03 | EMA 策略与回测序列有单测；绘图可 mock 测试。 |
| NFR-V4-04 | 回测与绘图性能在合理范围内。 |

---

## 6. 术语表

沿用项目既有术语，新增如下：

| 术语 | 英文 | 说明 |
|------|------|------|
| 黄金交叉 | Golden Cross | 短期 EMA 上穿长期 EMA，视为买入信号。 |
| 死亡交叉 | Death Cross | 短期 EMA 下穿长期 EMA，视为卖出信号。 |
| 趋势增强策略 | Trend Enhancement | 以长期 EMA 定趋势，再以波动率过滤，仅在「上升趋势 + 低波动」时持仓。 |
| 按日序列 | Daily Series | 回测产出的按交易日索引的 DataFrame，含权益、仓位、累计收益等。 |
| 累计收益倍数 | Cumulative Return (multiple) | 从 1 开始的累计收益，如 1.5 表示 50% 收益。 |

---

## 7. 需求可追溯性矩阵（RTM）

| 本 SRS 需求 | 上游来源 | 代码/配置影响 |
|-------------|----------|----------------|
| FR-V4-01 | nasdaq_v1 策略与 config | strategy/（新策略类）、strategy/factory.py、config/strategy.yaml、backtest/runner（预计算 EMA/vol） |
| FR-V4-02 | 回测可视化需求 | backtest/runner.py |
| FR-V4-03 | nasdaq_v1 plot 能力 | 新建 plot/ 或 viz 模块 |
| FR-V4-04 | 用户体验 | ndx_rsi/cli_main.py、README |

---

## 8. 需求变更日志

| 版本 | 日期 | 变更说明 | 作者/来源 |
|------|------|----------|-----------|
| 1.0 | 2026-02-12 | 初版 v4 PRD：EMA 策略集成、回测按日序列、回测后可视化、CLI 扩展 | 步骤 2 产出 |

---

**下一步**：本步骤完成后，请确认需求文档内容是否准确；确认后将进入「步骤 3：技术栈选择」与「步骤 4：技术方案设计」。
