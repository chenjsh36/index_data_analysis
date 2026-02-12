# 技术栈选型文档（Technology Stack Selection）— v4 EMA 策略与回测可视化集成

**文档版本**：1.0  
**产出日期**：2026-02-12  
**依据**：研发流程步骤 3 - 技术栈选择  
**上游输入**：`v4/02-requirements-documentation.md`、index_data_analysis 现有技术栈、nasdaq_v1 实现

---

## 1. 选型结论总览

**v4 需求（EMA 策略集成 + 回测按日序列 + 回测后可视化）在现有技术栈基础上做增量选型即可完成，无需引入新语言或新架构。**

- **策略与回测**：沿用现有 Python + pandas + 自研回测 runner + YAML 配置，仅扩展返回值与策略实现。
- **可视化**：新增 **matplotlib** 作为回测后图表的唯一依赖，与 nasdaq_v1 一致，便于移植与风格统一。
- **数据与指标**：EMA、波动率等均用 pandas 原生能力（`ewm`、`rolling`、`pct_change`），无需 TA-Lib 或额外指标库。

---

## 2. 技术栈沿用与新增清单

| 层次 | 选型 | v4 使用方式 |
|------|------|-------------|
| 开发语言 | Python 3.9+ | 不变，新策略与绘图模块均用 Python |
| 数据处理 | pandas, numpy | 不变；EMA 用 `df['close'].ewm(span=n, adjust=False).mean()`，波动率用 `daily_return.rolling(20).std()` |
| 数据源 | yfinance | 不变，EMA 策略复用现有 YFinanceDataSource 与 preprocess_ohlcv |
| 回测 | 自研 runner（ndx_rsi/backtest/runner.py） | **扩展**：循环内记录按日 equity/position/累计收益，可选返回 `(dict, series_df)` |
| 配置 | YAML（PyYAML） | **扩展**：新增 EMA_cross_v1、EMA_trend_v2 策略配置块 |
| 测试 | pytest | 不变，新增 EMA 策略与序列输出的单测 |
| **可视化** | **matplotlib** | **新增**：回测后累计收益图、EMA+买卖点图、多策略对比图；与 nasdaq_v1 的 plot 风格对齐 |

---

## 3. 新增技术选型：可视化（matplotlib）

### 3.1 选型结论

采用 **matplotlib** 作为 v4 回测后可视化的唯一绘图库。

### 3.2 评估

| 维度 | 评估 |
|------|------|
| 与需求匹配 | FR-V4-03 要求累计收益曲线、可选 EMA+买卖点、多策略对比；matplotlib 足以覆盖折线图、散点图与图例。 |
| 与 nasdaq_v1 一致 | nasdaq_v1 已用 matplotlib 实现 `plot_cumulative_returns`、`plot_ema_signals`、`plot_compare_v1_v2`，移植或参考时零额外学习成本。 |
| 依赖与体积 | 单库、无后端服务；index_data_analysis 当前 requirements.txt 未包含，需新增一行，对环境影响小。 |
| 输出方式 | 支持 `plt.show()` 弹窗与 `plt.savefig()` 保存 PNG，满足「显示与保存」需求。 |
| 非 GUI 环境 | 若在无显示环境运行，可配置 `matplotlib.use('Agg')`，仅保存文件不弹窗。 |

### 3.3 备选方案与取舍

| 备选 | 取舍 | 原因 |
|------|------|------|
| Plotly / Bokeh | 不采用 | 交互图对当前「回测后看图」非必需；增加依赖与复杂度；nasdaq_v1 为 matplotlib，统一更易维护。 |
| Seaborn | 不采用 | 折线图与散点图 matplotlib 原生即可；Seaborn 更适合统计图，本需求不涉及。 |
| 仅保存 JSON/CSV 不做图 | 不采用 | 需求明确要求「回测后可视化」与「累计收益图」，图表为交付物之一。 |

### 3.4 依赖与版本

- **matplotlib**：建议 `>=3.7.0`，与 nasdaq_v1 的 requirements.txt 一致，保证 API 稳定。
- 实施时在 `index_data_analysis/requirements.txt` 中新增：`matplotlib>=3.7.0`。

---

## 4. v4 需求与技术栈映射

| v4 需求 | 涉及技术 | 说明 |
|---------|----------|------|
| FR-V4-01 EMA 策略实现与接入 | Python + pandas + YAML | 新策略类用 pandas 读预计算列；EMA/vol 在 runner 中用 `ewm`/`rolling` 预计算；配置用现有 PyYAML |
| FR-V4-02 回测按日序列输出 | Python + pandas | runner 循环内 append 每行到 list，最后组 DataFrame；无新依赖 |
| FR-V4-03 回测后可视化 | **matplotlib** | 新建 plot 模块，接受 series_df 与可选 OHLCV+EMA，调用 pyplot 绘图 |
| FR-V4-04 CLI 扩展 | 无新依赖 | argparse 已有；新增子命令或 `--plot` 参数，内部调 run_backtest(return_series=True) + plot 模块 |

---

## 5. 指标实现方式（EMA / 波动率）

| 指标 | 实现方式 | 依赖 | 说明 |
|------|----------|------|------|
| EMA（50/80/200） | `df['close'].ewm(span=n, adjust=False).mean()` | pandas（已有） | 与 nasdaq_v1 的 data.py 一致 |
| 日收益率 | `df['close'].pct_change()` | pandas（已有） | 用于波动率与基准收益 |
| vol_20（20 日波动率） | `df['daily_return'].rolling(20).std()` | pandas（已有） | v2 策略过滤用 |

以上均不需 TA-Lib；现有项目若未安装 TA-Lib，不影响 v4 开发与运行。

---

## 6. 是否涉及 UI 与设计系统

- **v4 可视化形态**：回测结束后生成**静态图表**（累计收益曲线、EMA+买卖点），通过 matplotlib 弹窗或保存为 PNG 文件，**不涉及网站、App、中后台或落地页等交互式 UI**。
- **结论**：不涉及步骤 3 规范中的「涉及 UI 时的设计规范与设计系统」；**不需要**在本步骤调用 ui-ux-pro-max 或生成 design-system/MASTER.md。
- 若后续在 v4 之外增加 Web 监控面板或交互式看板，再在彼时的技术栈选型中引入前端技术并视情况生成设计系统。

---

## 7. 风险评估与缓解

| 风险 | 评估 | 缓解 |
|------|------|------|
| 回测循环内记录序列导致内存或性能下降 | 低 — 按日 append 列表，最后一次组 DataFrame，日线 20 年约 5000 行，可忽略 | 若未来支持分钟级再评估分块或采样 |
| 新增 matplotlib 导致 CI/无头环境报错 | 低 | 测试或 CI 中设置 `matplotlib.use('Agg')`，不调 `plt.show()` |
| EMA 策略与 nasdaq_v1 结果差异 | 中 — 需保证信号与止损逻辑一致 | 单测 + 与 nasdaq_v1 同参数回测对比，差异控制在验收范围内（如累计收益 <1%） |

---

## 8. 依赖清单（v4 增量）

在 **不改变** 现有 index_data_analysis 依赖的前提下，**新增** 以下即可支撑 v4：

```
# 回测后可视化（v4 新增）
matplotlib>=3.7.0
```

其余（Python 3.9+、pandas、numpy、yfinance、PyYAML、pytest）已满足，无需升级或新增。

---

## 9. 检查点

| 检查项 | 状态 |
|--------|------|
| 是否需要新技术/新语言？ | 否 |
| 是否新增依赖包？ | 是 — 仅 matplotlib |
| 现有技术栈是否满足全部 v4 需求？ | 是（含 matplotlib 后） |
| 是否涉及网站/App/中后台等 UI？ | 否 — 仅静态图表 |
| 是否需要在本步骤生成设计系统？ | 否 |

---

## 10. 输出物

| 输出物 | 状态 |
|--------|------|
| 技术栈选型文档 | ✅ 本文档 |
| 技术选型评估（可视化等） | ✅ 第 3、4 节 |
| 技术栈对比与取舍 | ✅ 第 3.3 节 |
| 依赖清单（v4 增量） | ✅ 第 8 节 |
| 设计系统 | 不适用（无交互式 UI） |

---

**下一步**：确认技术栈选型后，进入「步骤 4：技术方案设计」，产出 v4 的详细技术方案（EMA 策略类设计、回测扩展接口、可视化模块接口与 CLI 变更）。
