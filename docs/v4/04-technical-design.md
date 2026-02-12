# 技术方案设计（Technical Design）— v4 EMA 策略与回测可视化集成

**文档版本**：1.0  
**产出日期**：2026-02-12  
**依据**：研发流程步骤 4 - 技术方案设计  
**上游输入**：`v4/02-requirements-documentation.md`、`v4/03-technology-stack-selection.md`、现有 ndx_rsi 架构  
**设计原则**：增量扩展 — 不改变现有 NDX RSI 策略与回测默认行为，仅新增策略类、扩展 runner 返回值、新增可视化模块与 CLI 选项

---

## 一、修改范围总览

```
index_data_analysis/
├── config/
│   └── strategy.yaml                    [修改] 新增 EMA_cross_v1、EMA_trend_v2 策略配置块
├── ndx_rsi/
│   ├── strategy/
│   │   ├── base.py                     [不变] 接口已支持 current_position_info（可选）
│   │   ├── factory.py                  [修改] 根据策略名创建 EMA 策略实例
│   │   ├── ndx_short.py                [不变]
│   │   └── ema_cross.py                [新建] EMA 交叉 v1、趋势增强 v2 策略类
│   ├── backtest/
│   │   └── runner.py                   [修改] 按策略预计算 EMA/vol；可选返回 (dict, series_df)
│   ├── plot/                           [新建] 可视化模块
│   │   ├── __init__.py
│   │   └── backtest_plots.py           [新建] 累计收益图、多策略对比、可选 EMA+买卖点
│   └── cli_main.py                     [修改] run_backtest 支持 --plot/--save-plot；run_signal 支持 EMA 策略（预计算 ema/vol、拉取 400 日历史）
├── requirements.txt                    [修改] 新增 matplotlib>=3.7.0
└── README.md                           [修改] 补充 EMA 策略与可视化用法
```

---

## 二、数据流图（v4 扩展后）

```
                    ┌─────────────────────┐
                    │ config/strategy.yaml │ ← 新增 EMA_cross_v1 / EMA_trend_v2
                    └──────────┬──────────┘
                               │
  历史数据(yfinance) → 预计算指标 ──┬──→ 策略 generate_signal / calculate_risk
                    │              │
         ┌──────────┴──────────┐   │     ┌─────────────────────────────────┐
         │ NDX: ma50, rsi, vol │   │     │ 回测循环：equity / position /     │
         │ EMA v1: ema_50,200  │   └────→│ benchmark_cum 按日记录           │
         │ EMA v2: ema_80,200, │         │ return_series=True → series_df   │
         │         vol_20      │         └──────────────┬──────────────────┘
         └─────────────────────┘                        │
                                                        ▼
                                         ┌──────────────────────────────┐
                                         │ plot 模块：累计收益 / 对比 /   │
                                         │ EMA+买卖点（可选）             │
                                         └──────────────────────────────┘
```

---

## 三、各模块详细设计

### 3.1 配置层：`config/strategy.yaml`

在现有 `strategies` 下新增两个策略块，与 nasdaq_v1 的 config 对齐。

**新增配置结构**：

```yaml
strategies:
  # ... 现有 NDX_short_term 不变 ...

  EMA_cross_v1:
    index_code: "QQQ"
    # 均线周期（与 nasdaq_v1 SHORT_EMA, LONG_EMA 一致）
    short_ema: 50
    long_ema: 200
    # 调仓频率：daily | monthly
    rebalance_freq: "daily"
    # 止损比例（如 0.05 表示 5%）
    stop_loss_ratio: 0.05
    risk_control:
      stop_loss_ratio: 0.05
      take_profit_ratio: 0.20   # 可选，EMA 策略以交叉/止损为主

  EMA_trend_v2:
    index_code: "QQQ"
    ema_fast: 80
    ema_slow: 200
    vol_window: 20
    vol_threshold: 0.02        # 20 日波动率 < 2% 视为低波动
    risk_control:
      stop_loss_ratio: 0.05   # 备用
      take_profit_ratio: 0.20
```

**向后兼容**：仅新增键，不改动现有 NDX_short_term；`get_strategy_config("EMA_cross_v1")` 等由 config_loader 自然支持。

---

### 3.2 策略层：`ndx_rsi/strategy/ema_cross.py`（新建）

实现两个策略类，均实现 `BaseTradingStrategy`，与 `ndx_short.py` 一样支持 `generate_signal(data, current_position_info=None)` 和 `calculate_risk(signal, data)`。

#### 3.2.1 数据约定

- **EMA_cross_v1**：`data` 必须包含列 `close`、`ema_50`、`ema_200`（列名可从 config 的 short_ema/long_ema 推导为 `ema_{short_ema}`、`ema_{long_ema}`）。
- **EMA_trend_v2**：`data` 必须包含 `close`、`ema_80`、`ema_200`、`vol_20`（或由 config 的 ema_fast/ema_slow/vol_window 推导）。

#### 3.2.2 EMA Crossover v1 逻辑（与 nasdaq_v1 signals.generate_signals 对齐）

- **黄金交叉**：当前 bar 的 short_ema > long_ema，且前一根 short_ema <= long_ema → 买入，`position=1`，`reason="golden_cross"`。
- **死亡交叉**：当前 bar 的 short_ema < long_ema，且前一根 short_ema >= long_ema → 卖出，`position=0`，`reason="death_cross"`。
- **月度调仓**（`rebalance_freq == "monthly"`）：仅当当前日期为「当月最后一个交易日」时根据 short_ema 与 long_ema 大小决定 position（> 则 1，否则 0）；非月末日保持上一日仓位（需从 `current_position_info` 或上一日状态推断，实现上可在 window 内维护或简化为仅月末输出信号、其余日输出 hold）。
- **止损**：由回测 runner 统一根据 `calculate_risk` 返回的 `stop_loss` 执行；策略侧只需在 `calculate_risk` 中根据 config 的 `stop_loss_ratio` 返回 `stop_loss=当前价 * (1 - stop_loss_ratio)`，`take_profit` 可设为较大值或当前价 * 1.2。
- **信号在次日生效**：与现有 runner 一致，runner 用 `pos_new` 在下一 bar 生效；策略只需输出当日信号，无需 shift。

**接口**：

- `generate_signal(window, current_position_info=None)`  
  - 输入：`window` 为到当前 bar 为止的 DataFrame（含 ema_50、ema_200、close），最后一行为当前 bar。  
  - 输出：`{"signal": "buy"|"sell"|"hold", "position": 0|1, "reason": str}`。
- `calculate_risk(signal, data)`  
  - 返回 `{"stop_loss": float, "take_profit": float}`，基于 `data` 最后一行 close 与 config 的 stop_loss_ratio/take_profit_ratio。

#### 3.2.3 EMA Trend v2 逻辑（与 nasdaq_v1 signals.generate_signals_v2 对齐）

- **上升趋势**：ema_fast > ema_slow → 1，否则 0。
- **低波动**：vol_20 < vol_threshold → 1，否则 0。
- **持仓**：仅当「上升趋势 + 低波动」时 `position=1`，否则 `position=0`。  
- 信号在次日生效：与 nasdaq_v1 一致用 shift(1)；在逐 bar 调用时，策略对「当前 bar」输出的是基于当前 bar 的 0/1，runner 会在下一 bar 应用，因此逻辑上等价。
- `calculate_risk`：同上，返回 stop_loss/take_profit 供 runner 使用（v2 可能很少触发，但接口统一）。

#### 3.2.4 策略工厂扩展：`ndx_rsi/strategy/factory.py`

- 在 `create_strategy(strategy_name)` 中增加分支：
  - 若 `strategy_name == "EMA_cross_v1"`：`return EMA CrossoverV1Strategy(config)`（或类名如 `EMACrossoverV1Strategy`）。
  - 若 `strategy_name == "EMA_trend_v2"`：`return EMATrendV2Strategy(config)`。
- 使用 `get_strategy_config(strategy_name)` 获取 config，与 NDX_short_term 一致。

---

### 3.3 回测层：`ndx_rsi/backtest/runner.py` 扩展

#### 3.3.1 预计算指标按策略分派

在拉取并 preprocess 完 `df` 后，按 `strategy_name` 决定预计算列：

- **NDX_short_term**（或未识别为 EMA 时）：保持现有逻辑，计算 ma50、ma5、ma20、rsi_9、rsi_24、volume_ratio。
- **EMA_cross_v1**：  
  - 计算 `df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()`，`df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()`。  
  - 可从 config 读 short_ema/long_ema，默认 50/200。  
  - 预热期：至少 200 根 bar 后再开始回测循环（即 loop 从 `max(50, 200)` 或统一从 200 开始，与 nasdaq_v1 一致）。
- **EMA_trend_v2**：  
  - 计算 ema_80、ema_200、daily_return、vol_20（日收益率 rolling(20).std()）。  
  - 预热期同上，从 200 开始。

**实现建议**：在 `run_backtest` 内，在 `create_strategy` 之后、循环之前，根据 `strategy_name` 做 if/elif 分支，仅对 EMA 策略追加上述列；避免在 NDX 分支里计算 EMA 以保持性能。

#### 3.3.2 按日序列收集（return_series=True）

- **新增参数**：`run_backtest(..., return_series: bool = False)`。
- **默认行为**：`return_series=False` 时，行为与当前完全一致，仅返回 `Dict[str, Any]`。
- **return_series=True 时**：  
  - 在循环内维护列表，例如 `series_rows: List[Dict]`，每 bar 结束后 append 一行：  
    - `date`：当前 bar 的日期（index 值）。  
    - `equity`：当前 bar 结束后的权益（即当前的 `equity` 变量）。  
    - `position`：当前 bar 结束后的仓位（即当前的 `position` 变量）。  
    - `benchmark_cum_return`：基准累计收益倍数，建议为 `df["close"].iloc[i] / df["close"].iloc[loop_start]`，其中 `loop_start` 为循环起始索引（如 200）。  
    - `strategy_cum_return`：与 `equity` 一致（因初始权益为 1.0）。  
  - 循环结束后，用 `pd.DataFrame(series_rows)` 并设置 `date` 为 index，得到 `series_df`。  
  - 返回 `(result_dict, series_df)`。

**series_df 列约定**（供可视化与测试）：

| 列名 | 类型 | 说明 |
|------|------|------|
| equity | float | 当日结束后权益（从 1.0 起） |
| strategy_cum_return | float | 与 equity 相同，累计收益倍数 |
| benchmark_cum_return | float | 买入持有累计收益倍数 |
| position | float | 当日结束后仓位（0 或 1 等） |

索引为 DatetimeIndex，与回测区间内每个交易日一一对应。

#### 3.3.3 返回值类型与兼容性

- 函数签名建议：  
  `def run_backtest(..., return_series: bool = False) -> Union[Dict[str, Any], Tuple[Dict[str, Any], pd.DataFrame]]`  
  或保持返回类型为 `Union[Dict, Tuple[Dict, pd.DataFrame]]`，文档注明 `return_series=True` 时返回元组。
- 现有调用方（如 `cli_main.cmd_run_backtest`）不传 `return_series`，仍只接收 dict，无需改动；仅在需要绘图时传 `return_series=True` 并解包元组。

---

### 3.4 可视化模块：`ndx_rsi/plot/`（新建）

#### 3.4.1 目录与依赖

- 新建包 `ndx_rsi/plot/`，`__init__.py` 中导出绘图函数，便于 `from ndx_rsi.plot import plot_cumulative_returns, ...`。
- 实现文件 `backtest_plots.py`，依赖：matplotlib、pandas。  
- 绘图风格与 nasdaq_v1 的 `plot.py` 对齐：图例、网格、日期轴格式（如 YearLocator）、标题与轴标签。

#### 3.4.2 接口设计

**1）累计收益对比图（单策略）**

```python
def plot_cumulative_returns(
    series_df: pd.DataFrame,
    *,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    show: bool = True,
) -> None:
```

- `series_df`：须含 `strategy_cum_return`、`benchmark_cum_return`，index 为日期。
- 绘制两条曲线：基准、策略；图例 "Buy & Hold (Benchmark)"、"Strategy"。
- 若 `save_path` 非空则 `plt.savefig(save_path, dpi=150, bbox_inches="tight")`；若 `show` 为 True 则 `plt.show()`。
- 无 GUI 环境时调用方应设 `show=False`，仅保存文件。

**2）多策略对比图**

```python
def plot_compare_strategies(
    series_df_by_name: Dict[str, pd.DataFrame],
    *,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    show: bool = True,
) -> None:
```

- `series_df_by_name`：策略名 → 该策略的 series_df（每表含 `strategy_cum_return`，可选含 `benchmark_cum_return`；若多条均含 benchmark，仅绘制一次基准线即可）。
- 在同一图上绘制基准（若有）+ 各策略的 strategy_cum_return，图例为策略名。

**3）EMA + 买卖点图（可选）**

- 若 v4 首版实现，接口可为：  
  `plot_ema_signals(series_df: pd.DataFrame, ohlcv_ema_df: pd.DataFrame, *, title=None, save_path=None, show=True)`  
  其中 `ohlcv_ema_df` 含 close、ema_50、ema_200（或 ema_80）、以及可选 signal 列（1/-1/0）。  
- 需要 runner 在 `return_series=True` 时可选地附带或单独返回「带 signal 的序列」或由调用方从策略再跑一遍得到；若首版不实现该图，可在文档中写为「后续迭代」。

#### 3.4.3 与 nasdaq_v1 的差异

- 输入为 index_data_analysis 的 `series_df`（列名、索引约定见上），不直接依赖 nasdaq_v1 的 DataFrame 结构。
- 标题/图例可接受参数（如 strategy_name、symbol），由 CLI 或调用方传入。

---

### 3.5 CLI：`ndx_rsi/cli_main.py` 扩展

#### 3.5.1 run_backtest 子命令

- **策略名**：`--strategy` 已存在，允许的值新增 `EMA_cross_v1`、`EMA_trend_v2`；无需改参数定义，仅需 factory 支持。
- **可视化**：  
  - 新增可选参数 `--plot`：回测完成后若传入，则调用 `run_backtest(..., return_series=True)`，解包得到 `series_df`，再调用 `plot_cumulative_returns(series_df, show=True)`（不保存）。  
  - 新增可选参数 `--save-plot PATH`：同上，但调用 `plot_cumulative_returns(..., save_path=PATH, show=False)`。  
  - 二者可互斥或允许同时存在（先 save 再 show 或仅其一），建议：`--plot` 仅弹窗，`--save-plot` 仅保存；若同时传则保存且不弹窗（避免无头环境报错）。

#### 3.5.2 调用顺序

1. 解析 `run_backtest` 的 `--strategy --symbol --start --end` 及 `--plot` / `--save-plot`。  
2. 若存在 `--plot` 或 `--save-plot`，则 `result, series_df = run_backtest(..., return_series=True)`；否则 `result = run_backtest(...)`。  
3. 打印 `result`（与现有一致）。  
4. 若有 `--plot` 或 `--save-plot`，则根据参数调用 `plot_cumulative_returns(series_df, ...)`。

#### 3.5.3 run_signal 子命令（当前信号）

- **策略名**：`--strategy` 支持 `EMA_cross_v1`、`EMA_trend_v2` 与 `NDX_short_term`。
- **数据拉取**：EMA 策略需 200+ 根 K 线（如 ema_200），默认 `get_realtime_data()` 仅约 120 日；对 `EMA_cross_v1` / `EMA_trend_v2` 改为拉取约 400 个自然日历史，再预计算 ema/vol，用最后一根 K 线生成当前信号与风控。
- **预计算**：与 runner 一致，按策略名分支预计算 `ema_50`/`ema_200`（v1）或 `ema_80`/`ema_200`/`vol_20`（v2），再调用 `strategy.generate_signal(df)`、`strategy.calculate_risk(sig, df)` 并打印。

---

## 四、关键接口汇总

| 接口 | 说明 |
|------|------|
| `run_backtest(..., return_series=False)` | 默认仅返回 dict。`return_series=True` 时返回 `(dict, series_df)`。 |
| `series_df` 列 | 至少：index=日期，`equity`，`strategy_cum_return`，`benchmark_cum_return`，`position`。 |
| `plot_cumulative_returns(series_df, title=..., save_path=..., show=...)` | 单策略累计收益图。 |
| `plot_compare_strategies(series_df_by_name, ...)` | 多策略对比图。 |
| `create_strategy("EMA_cross_v1")` / `create_strategy("EMA_trend_v2")` | 返回对应策略实例。 |

---

## 五、预热期与数据长度

- EMA 策略需要 200 根 bar 才能得到有效 ema_200；runner 内循环起始索引建议为 `start_idx = 200`（或从 config 读 long_ema 取 max(50, long_ema)）。  
- 若 `len(df) < start_idx`，直接返回 `{"error": "insufficient_data", ...}`，与现有 `len(raw) < 60` 的不足数据处理一致；EMA 策略可要求 `len(df) >= 200`。

---

## 六、测试要点

- **策略单测**：构造带 ema_50、ema_200、close 的 DataFrame，验证黄金/死亡交叉时 `generate_signal` 输出 position 与 reason；v2 验证 uptrend+low_vol 组合。
- **回测扩展**：对固定 strategy_name 与固定日期区间，断言 `run_backtest(..., return_series=True)` 返回的 series_df 行数、列存在性、以及 series_df["strategy_cum_return"].iloc[-1] 与 result_dict["total_return"] 一致（即 (1 + total_return) 与最后一日的 strategy_cum_return 一致）。
- **可视化**：mock series_df 调用 `plot_cumulative_returns(..., show=False, save_path="/tmp/test.png")`，断言文件存在且可读（可选：简单检查文件大小 > 0）。

---

## 七、风险与注意事项

| 风险 | 缓解 |
|------|------|
| EMA 策略与 nasdaq_v1 结果差异 | 单测 + 同参数回测对比；差异主要来自 runner 的 Bar 内止损/手续费，可接受小幅偏差（如 <1%）。 |
| 月度调仓实现复杂 | 首版可在策略内判断「当月最后交易日」用 `window.index[-1]` 与当月最后一天比较；或先仅实现 daily，月度作为配置项后续加。 |
| 无 GUI 环境 plt.show() 报错 | CLI 使用 `--save-plot` 时只保存不 show；或在 plot 模块内检测 backend，若为 Agg 则默认不 show。 |

---

## 八、输出物与检查点

| 输出物 | 状态 |
|--------|------|
| 技术设计文档 | ✅ 本文档 |
| 架构/数据流说明 | ✅ 第一、二节 |
| 模块与接口设计 | ✅ 第三节 |
| 关键接口汇总 | ✅ 第四节 |

---

**下一步**：确认技术方案后，进入「步骤 5：开发步骤拆分」，产出 v4 的开发任务清单与实现顺序。
