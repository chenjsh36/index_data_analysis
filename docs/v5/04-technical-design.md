# 技术方案设计（Technical Design）— v5 信号可读化与推导逻辑展示

**文档版本**：1.0  
**产出日期**：2026-02-12  
**依据**：研发流程步骤 4 - 技术方案设计  
**上游输入**：`v5/02-requirements-documentation.md`、`v5/03-technology-stack-selection.md`、ndx_rsi 现有 CLI 与 run_signal 流程  
**设计原则**：展示层与策略解耦 — 不修改策略类接口，仅增加「报告格式化」逻辑，由 CLI 在得到 sig/risk 后调用并打印

---

## 一、修改范围总览

```
index_data_analysis/ndx_rsi/
├── report/                        [新建] 信号报告格式化
│   ├── __init__.py
│   └── signal_report.py           [新建] 可读报告与推导逻辑的拼装与打印
└── cli_main.py                    [修改] cmd_run_signal 改为调用 report 模块输出，不再直接 print(sig/risk)
```

策略层、回测层、配置层均不修改。

---

## 二、数据流

```
cmd_run_signal
    │
    ├── 拉取/预计算 → df
    ├── strategy.generate_signal(df) → sig
    ├── strategy.calculate_risk(sig, df) → risk
    │
    └── format_and_print_signal_report(strategy_name, symbol, df, sig, risk)
              │
              ├── row = df.iloc[-1], date = df.index[-1]
              ├── 按 strategy_name 分支：
              │     ├── EMA_cross_v1 → 取 ema_50, ema_200；选推导模板(reason)；拼报告
              │     ├── EMA_trend_v2 → 取 ema_80, ema_200, vol_20, 阈值；选推导模板；拼报告
              │     └── NDX_short_term → 取 ma50, rsi_9, rsi_24, volume_ratio 等；选推导模板；拼报告
              │
              └── print(报告字符串)
```

---

## 三、模块设计

### 3.1 报告模块：`ndx_rsi/report/signal_report.py`

**职责**：根据策略名、当前行数据（row）、sig、risk（及可选策略配置）生成可读报告字符串，并可选地执行打印。

**建议接口**：

```python
def format_signal_report(
    strategy_name: str,
    symbol: str,
    df: pd.DataFrame,
    sig: Dict[str, Any],
    risk: Dict[str, Any],
    strategy_config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    生成 run_signal 的可读报告（含推导逻辑）。
    df 至少含最后一根 K 线及该策略已预计算的指标列。
    """
```

- **入参**：`strategy_name`（如 `EMA_trend_v2`）、`symbol`（如 QQQ）、`df`（已含指标）、`sig`、`risk`；`strategy_config` 可选，用于展示阈值等。
- **返回**：一整块可打印的字符串（含分隔线、标题、多行标签与数值、推导逻辑、操作建议、止损止盈）。
- **实现要点**：
  - 取 `row = df.iloc[-1]`，`date = df.index[-1]`（格式化为 YYYY-MM-DD 或保留时间戳视需求）。
  - 按 `strategy_name` 分支，每支内：
    - 取该策略需要的指标列（若缺失则填空或 N/A）。
    - 根据 `sig["reason"]`（及 `sig["position"]`）选择推导逻辑模板，填入 `row` 与配置中的数值，得到「推导逻辑」字符串。
    - 将「操作建议」从 position/signal 转为中文（如 position=1 → 满仓持有，position=0 → 空仓观望）。
  - 统一版式：`"=" * 55`、标题行 `【{symbol} {策略显示名} 信号 - {date}】`、多行 `  标签: 数值`、`  推导逻辑: ...`、`  操作建议: ...`、`  止损: ...`、`  止盈: ...`、结尾分隔线。

**可选**：提供 `print_signal_report(...)`，内部调用 `format_signal_report` 后 `print(...)`，供 CLI 一行调用。

### 3.2 各策略报告与推导模板约定

#### EMA_cross_v1

- **展示字段**：当前日期、收盘价、EMA50、EMA200、推导逻辑、操作建议、止损、止盈。
- **推导逻辑**（按 `sig["reason"]` 选择模板，填入 row 及前一根的 ema 值）：
  - `golden_cross` → "EMA50({v1}) 上穿 EMA200({v2}) → 黄金交叉 → 建议买入/持有"
  - `death_cross` → "EMA50({v1}) 下穿 EMA200({v2}) → 死亡交叉 → 建议卖出/空仓"
  - `hold` 且 position=1 → "EMA50 > EMA200，趋势向上，未发生交叉 → 维持持有"
  - `hold` 且 position=0 → "EMA50 < EMA200，趋势向下，未发生交叉 → 维持空仓"
  - `monthly_rebalance_*` → 对应月末调仓说明（可选简短一句）。

#### EMA_trend_v2

- **展示字段**：当前日期、收盘价、EMA80、EMA200、20日波动率、波动率阈值、推导逻辑、操作建议、止损、止盈。
- **推导逻辑**：
  - 先算：uptrend = row["ema_80"] > row["ema_200"]；low_vol = row["vol_20"] < threshold。
  - 模板示例："EMA80({v1}) > EMA200({v2}) → 上升趋势；vol_20({v3}) < {threshold} → 低波动；上升+低波动 → 满仓持有"（或高波动/下降趋势的对应组合）。

#### NDX_short_term

- **展示字段**：当前日期、收盘价、MA50、RSI(9)、RSI(24)、量能比（及可选市场环境）、推导逻辑、操作建议、止损、止盈。
- **推导逻辑**：按 `sig["reason"]` 映射到简短中文，例如 `no_signal` → "RSI/均线/量能未触发买卖条件 → 观望"；`golden_cross` → "RSI 金叉 + 量能确认 → 建议加仓"；`overbought`/`oversell` 等同理，用一两句说明「当前指标满足何种条件 → 对应建议」。

### 3.3 CLI 修改：`ndx_rsi/cli_main.py` 中 `cmd_run_signal`

- 在得到 `sig`、`risk` 后，**不再**执行 `print("Signal:", sig)`、`print("Risk:", risk)`。
- 改为：调用 `format_signal_report(strategy_name, symbol, df, sig, risk, get_strategy_config(strategy_name))`，得到字符串后 `print(报告)`。
- 若需保留「raw 输出」供调试，可通过 `--format raw` 或环境变量在「可读报告」与「仅打印 dict」之间切换（v5 首版可为仅可读报告，不实现 raw 切换亦可）。

---

## 四、关键接口汇总

| 接口 | 说明 |
|------|------|
| `format_signal_report(strategy_name, symbol, df, sig, risk, strategy_config=None) -> str` | 生成可读报告字符串（含推导逻辑）。 |
| 可选 `print_signal_report(...)` | 内部 format 后 print，供 CLI 调用。 |

---

## 五、扩展新策略时的约定

- 在 `signal_report.py` 中为 `format_signal_report` 增加 `elif strategy_name == "新策略名":` 分支。
- 在新分支内：定义该策略要展示的指标列、从 `sig["reason"]` 到推导模板的映射、以及 position/signal 到中文操作建议的映射。
- 无需修改策略类或工厂。

---

## 六、测试要点

- **单测**：构造最小 `df`（一行或两行）、固定 `sig`/`risk`，调用 `format_signal_report`，断言返回字符串包含预期日期、数值、推导关键词（如「黄金交叉」「上升趋势」）、操作建议、止损止盈。
- **策略覆盖**：对三种策略各至少一个 reason 做一次断言，确保推导逻辑与 reason 一致。

---

## 七、输出物与检查点

| 输出物 | 状态 |
|--------|------|
| 技术设计文档 | ✅ 本文档 |
| 模块与接口设计 | ✅ 第三节 |
| 各策略报告与推导模板约定 | ✅ 3.2 |

---

**下一步**：确认技术方案后，进入「步骤 5：开发步骤拆分」，产出 v5 任务清单与实现顺序。
