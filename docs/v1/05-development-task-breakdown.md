# 开发步骤拆分（Development Task Breakdown）

**文档版本**：1.0  
**产出日期**：2026-02-08  
**依据**：研发流程步骤 5 - 开发步骤拆分  
**上游输入**：`04-technical-design.md`、`02-requirements-documentation.md`

---

## 1. 任务清单（Task List）

以下任务按**依赖顺序**排列，满足 WBS 与可独立测试、可独立交付原则；估算采用 **Story Points（Fibonacci）**，优先级 **P0=必须首版**，**P1=应做**，**P2=可选**。

---

### T1. 项目骨架与配置层

| 属性 | 内容 |
|------|------|
| **任务 ID** | T1 |
| **任务名称** | 项目骨架与配置层 |
| **任务描述** | 创建 Python 项目结构（包划分、requirements.txt）、配置目录 `config/`，实现 `datasource.yaml` 与 `strategy.yaml` 的示例内容及 YAML 加载工具；支持通过策略名/指数名读取配置。 |
| **验收标准** | ① 项目可 `pip install -r requirements.txt` 安装依赖；② 存在 `config/datasource.yaml`、`config/strategy.yaml`，结构符合 TDD 2.1/2.4；③ 有配置加载函数/类，能按 key 返回对应 dict；④ 无业务逻辑，仅配置与加载。 |
| **依赖** | 无 |
| **估算** | 2 SP |
| **优先级** | P0 |

---

### T2. 数据层：BaseDataSource 与 YFinance 实现

| 属性 | 内容 |
|------|------|
| **任务 ID** | T2 |
| **任务名称** | 数据层：BaseDataSource 与 YFinance 实现 |
| **任务描述** | 定义 `BaseDataSource` 抽象类（get_historical_data、get_realtime_data）；实现 `YFinanceDataSource`，从 yfinance 拉取 NDX/QQQ/TQQQ 日线（及可选 30 分钟线），列名统一为 open/high/low/close/volume，索引 DatetimeIndex；前复权优先使用 Adj Close（若有）。 |
| **验收标准** | ① 给定 symbol 与日期范围，能返回含 OHLCV 的 DataFrame；② 列名与索引符合 TDD 3.1；③ 可通过配置选择 data_source（yfinance）；④ 单元测试：至少 1 个标的、短区间拉取成功。 |
| **依赖** | T1 |
| **估算** | 3 SP |
| **优先级** | P0 |

---

### T3. 数据预处理

| 属性 | 内容 |
|------|------|
| **任务 ID** | T3 |
| **任务名称** | 数据预处理 |
| **任务描述** | 在数据层内实现预处理：缺失值策略（日线缺失>2 周期标记异常）、量能比 volume_ratio 计算（volume/rolling(20).mean()，比值>3 时截断或替换）、列名与小写统一；可选：前复权逻辑封装为函数。 |
| **验收标准** | ① 预处理后 DataFrame 含 volume_ratio，无 NaN 或已标记异常；② 量能异常处理符合 TDD 2.7；③ 与 T2 集成后，数据层输出可直接供计算层使用。 |
| **依赖** | T2 |
| **估算** | 2 SP |
| **优先级** | P0 |

---

### T4. 计算层：RSI/MA/量能比手写与 TA-Lib 验证

| 属性 | 内容 |
|------|------|
| **任务 ID** | T4 |
| **任务名称** | 计算层：RSI/MA/量能比手写与 TA-Lib 验证 |
| **任务描述** | 实现手写 `calculate_rsi_handwrite(prices, period)`、`calculate_ma(series, window)`、`calculate_volume_ratio(volume, window=20)`；实现 `calculate_rsi_talib` 与 `verify_rsi(prices, period, max_diff=0.1)`；为 RSI(9)、RSI(24) 编写单测，验证手写与 TA-Lib 偏差≤0.1。 |
| **验收标准** | ① 手写 RSI 与 BRD 公式一致；② verify_rsi 在样本数据上返回 True（偏差≤0.1）；③ 单测覆盖 RSI 9/24、MA50、volume_ratio；④ 文档或注释说明计算步骤。 |
| **依赖** | T1 |
| **估算** | 5 SP |
| **优先级** | P0 |

---

### T5. 计算层：市场环境与 RSI 阈值

| 属性 | 内容 |
|------|------|
| **任务 ID** | T5 |
| **任务名称** | 计算层：市场环境与 RSI 阈值 |
| **任务描述** | 实现 `judge_market_env(prices, ma50)` 返回 bull/bear/oscillate/transition（逻辑与 design.md、TDD 2.2 一致）；实现 `get_rsi_thresholds(market_env)` 返回超买/超卖/强超买/强超卖阈值表；阈值可从配置读取或写死与 design 一致。 |
| **验收标准** | ① 对典型历史区间（如 2021 牛、2022 熊、2023 震荡）能正确输出环境标签；② 阈值与 design.md 中表一致；③ 单测至少 3 组价格+ma50 输入与预期环境。 |
| **依赖** | T4 |
| **估算** | 3 SP |
| **优先级** | P0 |

---

### T6. 信号层：趋势与量能规则

| 属性 | 内容 |
|------|------|
| **任务 ID** | T6 |
| **任务名称** | 信号层：趋势与量能规则 |
| **任务描述** | 实现趋势判定（50 日均线斜率 + 连续 2 日收盘价与 MA50 关系 → 上升/下降/震荡）；实现量能分类（放量≥1.2、缩量≤0.8、巨量≥1.5、地量≤0.5）。输出为可被信号层其他模块调用的布尔或枚举。 |
| **验收标准** | ① 趋势判定与 design.md 表一致；② 量能规则与 TDD 2.3 一致；③ 单测：给定 DataFrame 能返回趋势类型与当日量能类型。 |
| **依赖** | T5 |
| **估算** | 3 SP |
| **优先级** | P0 |

---

### T7. 信号层：RSI 信号（超买超卖、金叉死叉、背离）

| 属性 | 内容 |
|------|------|
| **任务 ID** | T7 |
| **任务名称** | 信号层：RSI 信号（超买超卖、金叉死叉、背离） |
| **任务描述** | 实现超买超卖判断（按市场环境阈值）；金叉/死叉（9 日上穿/下穿 24 日，含交叉区间与量能条件）；顶背离/底背离（价格高低点 + RSI 高低点 + 量能，与 design.md 量化条件一致）。输出统一为「信号类型 + 原因」结构，供组合逻辑使用。 |
| **验收标准** | ① 超买超卖、金叉死叉、背离判定与 design.md 一致；② 组合前各信号可单独单元测试；③ 与 T6 趋势/量能联合测试至少 2 组场景。 |
| **依赖** | T6 |
| **估算** | 8 SP |
| **优先级** | P0 |

---

### T8. 信号层：组合过滤与输出

| 属性 | 内容 |
|------|------|
| **任务 ID** | T8 |
| **任务名称** | 信号层：组合过滤与输出 |
| **任务描述** | 实现「趋势 > 量能 > RSI」组合逻辑：上升趋势忽略单纯超买（除非缩量滞涨）、下降趋势忽略单纯超卖（除非缩量企稳）；震荡市执行超买超卖高抛低吸；金叉死叉需量能验证。输出为 TDD 3.1 约定的 signal dict（signal, position, reason）。 |
| **验收标准** | ① 组合规则与 design.md 与 TDD 2.3 一致；② 输出结构含 signal/position/reason，可选 stop_loss/take_profit；③ 单测或小回测片段验证至少 3 种信号路径。 |
| **依赖** | T7 |
| **估算** | 5 SP |
| **优先级** | P0 |

---

### T9. 风控层

| 属性 | 内容 |
|------|------|
| **任务 ID** | T9 |
| **任务名称** | 风控层 |
| **任务描述** | 实现仓位上限（按市场环境）、止损止盈比例（按标的类型 ETF/杠杆 ETF 与策略配置）；极端行情检查（VIX>30 且 RSI<10 或 RSI>90 时禁止开仓）；回撤熔断（累计回撤≥10% 时降仓至 30% 并暂停 2 日）。与策略层集成：generate_signal 前做极端行情检查，calculate_risk 返回止损止盈。 |
| **验收标准** | ① 极端行情下不输出开仓类信号；② 止损止盈与 design.md 表一致；③ 回撤熔断在回测中可触发并验证；④ 有单测或回测用例。 |
| **依赖** | T8 |
| **估算** | 5 SP |
| **优先级** | P0 |

---

### T10. 策略层：BaseTradingStrategy 与 NDX 短线策略

| 属性 | 内容 |
|------|------|
| **任务 ID** | T10 |
| **任务名称** | 策略层：BaseTradingStrategy 与 NDX 短线策略 |
| **任务描述** | 定义 `BaseTradingStrategy` 抽象类（generate_signal、calculate_risk）；实现 `NDXShortTermRSIStrategy`，从 strategy_config 读取 RSI 周期与阈值，内部调用计算层（指标+环境）、信号层（规则+组合）、风控层，返回 signal dict 与 risk dict；实现 `StrategyFactory.create_strategy(name)` 从 config/strategy.yaml 加载并实例化。 |
| **验收标准** | ① 接口与 TDD 2.4 一致；② 给定含 close/volume/rsi_9/rsi_24/ma50/volume_ratio 的 DataFrame，能输出正确 signal 与 stop_loss/take_profit；③ Factory 能根据配置创建 NDX_short_term 策略。 |
| **依赖** | T9, T1 |
| **估算** | 5 SP |
| **优先级** | P0 |

---

### T11. 回测层：Backtrader 集成与绩效统计

| 属性 | 内容 |
|------|------|
| **任务 ID** | T11 |
| **任务名称** | 回测层：Backtrader 集成与绩效统计 |
| **任务描述** | 将数据层+计算层+策略层串联：拉取历史数据 → 预计算指标 → 按 Bar 推进，每 Bar 调用策略 generate_signal/calculate_risk，按信号与风控模拟成交；使用 Backtrader 或自研循环均可。统计胜率、盈亏比、最大回撤、年化收益、夏普比率；输出为 dict 或报表文件。 |
| **验收标准** | ① 回测 2018–2025 某标的（如 QQQ）可重复运行并得到稳定结果；② 输出含胜率、盈亏比、最大回撤、夏普等；③ 手续费/滑点可配置（如 0.05%）；④ 与设计文档绩效指标定义一致。 |
| **依赖** | T10, T2, T3 |
| **估算** | 8 SP |
| **优先级** | P0 |

---

### T12. CLI 入口

| 属性 | 内容 |
|------|------|
| **任务 ID** | T12 |
| **任务名称** | CLI 入口 |
| **任务描述** | 实现 CLI：fetch_data（拉取并可选保存）、run_backtest（执行回测并打印/保存结果）、run_signal（对最新数据生成信号并打印）、verify_indicators（运行 RSI 手写 vs TA-Lib 验证）。参数通过 argparse 或 click 解析，调用对应模块。 |
| **验收标准** | ① 上述 4 类命令可执行并输出符合预期；② 参数与 TDD 4.1 约定一致；③ README 或 --help 说明用法。 |
| **依赖** | T11, T10, T2, T4 |
| **估算** | 3 SP |
| **优先级** | P0 |

---

### T13. 单元测试与指标验证自动化

| 属性 | 内容 |
|------|------|
| **任务 ID** | T13 |
| **任务名称** | 单元测试与指标验证自动化 |
| **任务描述** | 为计算层、信号层、策略层补充 pytest 单测；指标验证（verify_rsi）纳入 CI 或本地 check；单测覆盖率目标≥90%（关键路径：RSI、MA、volume_ratio、趋势、信号组合、风控）。 |
| **验收标准** | ① pytest 通过；② 覆盖率报告显示核心模块≥90%；③ verify_rsi 在真实行情片段上通过。 |
| **依赖** | T4, T6, T7, T8, T9, T10 |
| **估算** | 5 SP |
| **优先级** | P1 |

---

### T14. 可选：SQLite 持久化

| 属性 | 内容 |
|------|------|
| **任务 ID** | T14 |
| **任务名称** | 可选：SQLite 持久化 |
| **任务描述** | 实现 SQLite 存储适配：ohlcv_cache、backtest_runs、可选 signals_log；fetch_data 可选落库，run_backtest 可选写入 backtest_runs；提供简单查询接口（如按 strategy_name 查最近回测结果）。 |
| **验收标准** | ① 表结构与 TDD 3.2 一致；② 能写入并读出回测结果与行情缓存；③ 不影响无持久化时的运行。 |
| **依赖** | T2, T11 |
| **估算** | 3 SP |
| **优先级** | P2 |

---

### T15. 可选：Docker 与运行说明

| 属性 | 内容 |
|------|------|
| **任务 ID** | T15 |
| **任务名称** | 可选：Docker 与运行说明 |
| **任务描述** | 编写 Dockerfile（基于 python:3.11-slim，安装 TA-Lib 依赖与项目依赖）；编写 README：安装、配置、CLI 用法、回测示例；可选 docker-compose 用于本地一键运行。 |
| **验收标准** | ① docker build 成功；② 容器内可执行 run_backtest 等命令；③ README 包含至少一种安装方式与回测示例。 |
| **依赖** | T12 |
| **估算** | 2 SP |
| **优先级** | P2 |

---

## 2. 任务依赖图（Dependency Graph）

```
                    T1 配置层
                   /   |   \
                  /    |    \
                 v     v     v
                T2    T4    T10
                 |     |     ^
                 v     v     |
                T3    T5    T9
                 |     |     ^
                 |     v     |
                 |    T6    T8
                 |     |     ^
                 |     v     |
                 |    T7 ---+
                 |     |
                 +---->T11<--+
                  \    |    /
                   \   v   /
                    T12 CLI
                      |
            +---------+---------+
            v         v         v
           T13       T14       T15
           测试     SQLite    Docker
```

**关键路径**：T1 → T2 → T3 → (T4→T5→T6→T7→T8→T9→T10) → T11 → T12。  
T4 可与 T2 并行开发（仅依赖 T1）；T10 依赖 T9 与 T1；T11 依赖 T10 与 T2/T3。

---

## 3. 开发计划（Development Plan）

按**阶段**组织，便于迭代交付与验收。

| 阶段 | 任务 | 目标 |
|------|------|------|
| **Phase 1：数据与指标** | T1, T2, T3, T4, T5 | 能拉取数据、预处理、计算 RSI/MA/量能比、判定市场环境与阈值，且 RSI 通过 TA-Lib 验证。 |
| **Phase 2：信号与策略** | T6, T7, T8, T9, T10 | 能对给定 DataFrame 输出完整 signal dict（含趋势+量能+RSI 组合与风控）。 |
| **Phase 3：回测与入口** | T11, T12 | 能运行历史回测并得到绩效报表，CLI 四类命令可用。 |
| **Phase 4：质量与可选** | T13, T14, T15 | 单测覆盖达标；可选持久化与 Docker 就绪。 |

**建议顺序**：Phase 1 全部完成后再进入 Phase 2；Phase 2 完成后做 Phase 3；T13 可与 Phase 2/3 并行推进（每完成一模块补单测）。

---

## 4. 里程碑计划（Milestone Plan）

| 里程碑 | 完成条件 | 目标日期（示例） |
|--------|----------|------------------|
| **M1：数据与指标可用** | T1–T5 完成；能从 yfinance 拉取 QQQ 数据并输出带 rsi_9/rsi_24/ma50/volume_ratio/market_env 的 DataFrame；verify_rsi 通过。 | 按项目排期 |
| **M2：信号与策略可用** | T6–T10 完成；对任意一段历史数据能输出符合 design 的 signal 与止损止盈；StrategyFactory 可创建 NDX_short_term。 | 按项目排期 |
| **M3：回测与 CLI 可用** | T11–T12 完成；run_backtest 对 2018–2025 产出绩效报表；run_signal、fetch_data、verify_indicators 可用。 | 按项目排期 |
| **M4：首版发布** | T13 完成（单测≥90%）；可选 T14/T15；文档与 README 满足交付要求；回测绩效满足 NFR-02（胜率≥62%、盈亏比≥1.5、回撤≤15% 或≤20%）。 | 按项目排期 |

---

## 5. 工作量汇总与优先级

| 优先级 | 任务数 | Story Points 合计 |
|--------|--------|-------------------|
| P0 | 12（T1–T12） | 52 SP |
| P1 | 1（T13） | 5 SP |
| P2 | 2（T14, T15） | 5 SP |

**说明**：1 SP ≈ 约 0.5–1 人天（视团队经验而定）；P0 完成后即可进行步骤 6 的代码开发与联调，P1/P2 可在首版迭代中或后续迭代完成。

---

## 6. 输出物清单

| 输出物 | 状态 |
|--------|------|
| 任务清单（Task List） | ✅ 第 1 节 |
| 任务依赖图（Dependency Graph） | ✅ 第 2 节 |
| 开发计划（Development Plan） | ✅ 第 3 节 |
| 里程碑计划（Milestone Plan） | ✅ 第 4 节 |

---

**下一步**：确认任务拆分与优先级后，进入「步骤 6：代码开发」。可按 Phase 或按任务 ID 分批开发，建议从 T1 开始。
