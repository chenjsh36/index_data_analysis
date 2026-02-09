# 技术栈选型文档（Technology Stack Selection）— v3 BRD 对齐修正版

**文档版本**：3.0  
**产出日期**：2026-02-09  
**依据**：研发流程步骤 3 - 技术栈选择  
**上游输入**：`v3/02-requirements-documentation.md`、`v1/03-technology-stack-selection.md`

---

## 1. 选型结论

**v3 修正需求（FIX-01 ~ FIX-13）不涉及新技术引入，沿用 v1 技术栈不变。**

v3 的全部改动集中在信号层（`signal/`）、风控层（`risk/`）和配置（`strategy.yaml`），属于纯业务逻辑修正和增强，不涉及新框架、新数据源或新架构模式。

---

## 2. 技术栈沿用清单（与 v1 完全一致）

| 层次 | 选型 | v3 影响 |
|------|------|---------|
| 开发语言 | Python 3.9+ | 无变化 |
| 数据处理 | pandas, numpy | 无变化，新增 MA5/MA20 用 pandas rolling 即可 |
| 数据源 | yfinance | 无变化 |
| 指标验证 | TA-Lib | 无变化，MA5/MA20 可纳入验证 |
| 回测 | 自研 runner（Backtrader 备选） | 无变化 |
| 配置 | YAML（PyYAML） | 新增配置项，格式不变 |
| 测试 | pytest | 新增测试用例，框架不变 |

---

## 3. v3 需求与技术栈映射

| v3 需求 | 涉及技术 | 说明 |
|---------|----------|------|
| FIX-01 ~ FIX-06（信号逻辑修正） | Python 业务逻辑 | 修改 `combine.py` 条件分支，无新依赖 |
| FIX-07（金叉/死叉确认增强） | pandas rolling | 新增 MA5 指标，用 `pd.Series.rolling(5).mean()` |
| FIX-08（超买超卖强度分级） | YAML 配置 + Python | 配置新增 `strong_overbuy/strong_oversell`，逻辑纯 Python |
| FIX-09（信号级止损止盈） | YAML 配置 + Python | 配置新增 `signal_risk` 分组，逻辑纯 Python |
| FIX-10（背离分趋势） | Python 业务逻辑 | 重构 `combine.py` 背离处理分支 |
| FIX-11（平仓信号） | Python 业务逻辑 | 信号生成增加持仓状态感知 |
| FIX-12（动态仓位上限） | YAML 配置 + Python | 配置新增 `dynamic_cap`，逻辑纯 Python |
| FIX-13（MA20 指标） | pandas rolling | 新增 MA20，用 `pd.Series.rolling(20).mean()` |

---

## 4. 新增指标实现方式

| 指标 | 实现方式 | 依赖 | 验证 |
|------|----------|------|------|
| MA5 | `df['close'].rolling(5).mean()` | pandas（已有） | 与 TA-Lib `SMA(close, 5)` 比对 |
| MA20 | `df['close'].rolling(20).mean()` | pandas（已有） | 与 TA-Lib `SMA(close, 20)` 比对 |

两个新指标均为简单移动平均，pandas 原生支持，无需引入任何新依赖。

---

## 5. 风险评估

| 风险 | 评估 | 缓解 |
|------|------|------|
| 新增逻辑导致回测性能下降 | 低 — MA5/MA20 计算开销极小（<1% 额外耗时） | 回测前后对比运行时间 |
| 配置变更导致旧配置不兼容 | 低 — 新增字段使用默认值 | 代码中对新配置项做 `.get()` 兜底 |
| 信号逻辑修改导致回测绩效波动 | 预期内 — 更严格的过滤预计减少交易次数 | 修正前后回测对比报告 |

---

## 6. 检查点

| 检查项 | 状态 |
|--------|------|
| 是否需要新技术/框架？ | 否 |
| 是否需要新依赖包？ | 否 |
| 现有技术栈是否满足全部 v3 需求？ | 是 |
| 是否涉及 UI？ | 否 |

---

**下一步**：确认后进入「步骤 4：技术方案设计」，产出 v3 修正的详细技术方案（信号层重构方案、配置变更方案、测试方案）。
