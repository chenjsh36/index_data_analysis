# 技术栈选型（步骤 3）— v7 纳指机构级策略

**文档类型**：技术栈选择  
**依据**：`docs/v7/02-requirements-documentation.md`  
**参考规范**：技术选型评估矩阵、FURPS+

---

## 1. 选型总览

v7 需求**仅涉及策略与指标扩展**（新策略 EMA_trend_v3、ADX/MACD/SMA200、信号报告），不涉及新 UI、定时任务或静态站点。技术栈以**沿用现有项目为主**，仅对新增指标实现方式做明确选型。

| 能力域 | 选型结论 | 说明 |
|--------|----------|------|
| 运行时与语言 | **Python 3.9+**（现有） | 与现有 ndx_rsi、回测、run_signal 一致 |
| 数据处理与指标 | **pandas / numpy**（现有）+ **ADX/MACD 手写实现** | 指标计算沿用“数据准备阶段写入 DataFrame 列”的模式；ADX、MACD 采用手写，不强制依赖 TA-Lib |
| 指标验证（可选） | **TA-Lib**（可选） | 与 RSI 一致：TA-Lib 可选用于 ADX/MACD 结果比对；未安装时不影响策略运行 |
| 配置 | **PyYAML + config/strategy.yaml**（现有） | 新策略增加配置段，沿用现有 config_loader |
| 数据源 | **yfinance**（现有）；VIX 可选 **^VIX** | 主标的数据不变；若实现 VIX，用同一 yfinance 拉取 ^VIX |
| 报告 | **ndx_rsi/report/signal_report.py**（现有） | 新增 EMA_trend_v3 分支，文本报告 + 可选 signal_report_to_dict 扩展 |

---

## 2. 技术栈明细与评估

### 2.1 新增指标：ADX、MACD

| 技术项 | 选型 | 评估维度 | 说明 |
|--------|------|----------|------|
| ADX 实现 | **pandas 手写**（+DM、-DM、TR、Wilder 平滑） | 依赖最小化、可维护性 | 与 v4 选型一致：核心指标不强制 TA-Lib，保证未安装 TA-Lib 时项目可完整运行；公式清晰，便于与 BRD 对照 |
| MACD 实现 | **pandas 手写**（EMA12、EMA26、MACD_line = EMA12 - EMA26） | 同上 | 仅需 ewm(span=...) 与差运算，无额外依赖 |
| 验证（可选） | **TA-Lib**（若已安装） | 正确性、与现有 RSI 验证模式一致 | 可选提供 `calculate_adx_talib`、`calculate_macd_talib` 及 verify 函数；未安装时跳过验证，不影响 run_signal/回测 |

**不选用**：将 TA-Lib 作为 ADX/MACD 的必选依赖（与 README 中“TA-Lib 可选”一致）。

### 2.2 策略、数据准备与报告

| 技术项 | 选型 | 说明 |
|--------|------|------|
| 策略基类与工厂 | **现有 BaseTradingStrategy、factory.py** | 新策略类继承 BaseTradingStrategy，在 factory 中按策略名返回实例 |
| 数据准备 | **现有 runner.py / cli_main.py 分支** | 按策略名分支，计算 ema_80、ema_200、vol_20、sma_200、adx_14、macd_line 等列；SMA200 复用 `calculate_ma(series, 200)` |
| 报告格式 | **与 _report_ema_trend_v2 一致的文本 + 可选 dict** | 分隔线、标题、指标逐行、五条件满足情况、推导逻辑、操作建议、止损止盈；可选 signal_report_to_dict 增加 v3 字段 |

### 2.3 VIX（可选）

| 技术项 | 选型 | 说明 |
|--------|------|------|
| VIX 数据源 | **yfinance** 拉取 **^VIX** | 与现有标的拉取同一库，无需新增依赖；取最近一个交易日收盘或最新价 |
| 传入方式 | **策略 config 或 generate_signal 关键字参数** | 由调用方（如 run_signal）拉取后写入 config 或传入 `vix=float`，策略内仅读 |

---

## 3. 技术选型评估简表

| 维度 | ADX/MACD 手写 | 可选 TA-Lib 验证 |
|------|----------------|------------------|
| 技术成熟度 | 高（公式标准、pandas 成熟） | 高（TA-Lib 广泛用于验证） |
| 依赖与部署 | 无新增必选依赖 | 可选，与现有 RSI 验证一致 |
| 可维护性 | 逻辑透明、易与 BRD 对照 | 便于回归与正确性检查 |
| 与现有架构一致性 | 与 v2/v4 指标“手写 + 可选验证”一致 | 与 ndx_rsi.indicators 现有模式一致 |

---

## 4. 约束与依赖

- **C-1**（需求文档）：采用方案 B，独立新策略类，不修改 EMA_trend_v2。
- **C-2**（需求文档）：所有新指标在数据准备阶段算好写入 DataFrame 列，策略只读。
- **现有依赖**：不新增必选 pip 依赖；若使用 TA-Lib 做 ADX/MACD 验证，沿用现有可选依赖说明（README、requirements.txt 注释）。
- **v7 不涉及 UI**：无需设计系统或前端技术选型。

---

## 5. 输出物与检查点

| 输出物 | 状态 |
|--------|------|
| 技术栈选型文档（本文档） | ✅ |
| 技术选型评估（上文第 3 节） | ✅ |
| 设计系统 | 不适用（v7 无 UI） |
| 文件名 | `03-technology-stack-selection.md`（本文档） |

- ✅ 从 v7 需求出发，明确 ADX/MACD 手写为主、TA-Lib 可选验证。
- ✅ 策略、数据准备、报告、VIX 均沿用现有技术栈，无冲突。
- ✅ 未引入新必选依赖。

**下一步**：完成本步骤后需用户确认；确认后进入步骤 4「技术方案设计」。
