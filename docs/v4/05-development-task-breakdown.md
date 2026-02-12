# 开发步骤拆分（Development Task Breakdown）— v4 EMA 策略与回测可视化集成

**文档版本**：1.0  
**产出日期**：2026-02-12  
**依据**：研发流程步骤 5 - 开发步骤拆分  
**上游输入**：`v4/04-technical-design.md`

---

## 一、里程碑计划

| 里程碑 | 包含任务 | 目标 |
|--------|----------|------|
| **M1 — 配置与策略** | TASK-01 ~ TASK-03 | 策略配置就绪、EMA 策略类实现并接入工厂 |
| **M2 — 回测扩展** | TASK-04 ~ TASK-05 | 按策略预计算指标、可选返回按日序列 |
| **M3 — 可视化与 CLI** | TASK-06 ~ TASK-07 | 绘图模块、CLI 回测后看图 |
| **M4 — 依赖与验证** | TASK-08 ~ TASK-09 | 依赖与文档、单测与回归 |

---

## 二、任务依赖图

```
TASK-01 (strategy.yaml 新增 EMA 配置)
   │
   ├──→ TASK-02 (ema_cross.py 策略类)
   │         │
   │         └──→ TASK-03 (factory 注册)
   │                   │
   │                   └──→ TASK-04 (runner 预计算 EMA/vol + 预热期)
   │                             │
   │                             └──→ TASK-05 (runner return_series + series_df)
   │                                       │
   │                                       ├──→ TASK-06 (plot 模块)
   │                                       │         │
   │                                       │         └──→ TASK-07 (CLI --plot/--save-plot)
   │                                       │
   │                                       └──→ TASK-09 (单测，可选依赖 T02)
   │
   └──→ TASK-08 (requirements + README，可与 T02 并行)
```

---

## 三、任务清单

### TASK-01: 策略配置新增 EMA_cross_v1 / EMA_trend_v2

| 字段 | 内容 |
|------|------|
| **ID** | TASK-01 |
| **名称** | 策略配置新增 EMA_cross_v1 / EMA_trend_v2 |
| **优先级** | P0 |
| **对应需求** | FR-V4-01 |
| **估算** | XS (0.25 天) |
| **依赖** | 无 |
| **描述** | 在 `config/strategy.yaml` 的 `strategies` 下新增两个策略块：1. `EMA_cross_v1`：short_ema=50, long_ema=200, rebalance_freq=daily, stop_loss_ratio=0.05，以及 risk_control 段。2. `EMA_trend_v2`：ema_fast=80, ema_slow=200, vol_window=20, vol_threshold=0.02，以及 risk_control 段。结构见 04-technical-design §3.1。 |
| **涉及文件** | `config/strategy.yaml` |
| **验收标准** | 1. `get_strategy_config("EMA_cross_v1")` 返回含 short_ema、long_ema、rebalance_freq、stop_loss_ratio 的 dict。2. `get_strategy_config("EMA_trend_v2")` 返回含 ema_fast、ema_slow、vol_window、vol_threshold 的 dict。3. 现有 NDX_short_term 配置与加载不受影响。 |

---

### TASK-02: 实现 EMA 策略类（ema_cross.py）

| 字段 | 内容 |
|------|------|
| **ID** | TASK-02 |
| **名称** | 实现 EMA 策略类（ema_cross.py） |
| **优先级** | P0 |
| **对应需求** | FR-V4-01 |
| **估算** | M (1 天) |
| **依赖** | TASK-01 |
| **描述** | 新建 `ndx_rsi/strategy/ema_cross.py`，实现两个类，均继承 `BaseTradingStrategy`。1. **EMACrossoverV1Strategy**：generate_signal(window, current_position_info=None) 根据 ema_50、ema_200 判断黄金/死亡交叉，输出 position 0 或 1 及 reason；支持 rebalance_freq=daily 或 monthly（月度时仅月末日根据均线输出信号）。calculate_risk(signal, data) 根据 config 的 stop_loss_ratio 返回 stop_loss、take_profit（如 stop_loss=close*(1-stop_loss_ratio), take_profit=close*1.2）。2. **EMATrendV2Strategy**：generate_signal 根据 ema_80>ema_200 且 vol_20<threshold 输出 position 1，否则 0。calculate_risk 同上。列名从 config 读取（如 short_ema/long_ema → ema_50/ema_200）。逻辑与 nasdaq_v1 的 signals.py 对齐。 |
| **涉及文件** | `ndx_rsi/strategy/ema_cross.py`（新建） |
| **验收标准** | 1. 给定含 ema_50、ema_200、close 的 window，黄金交叉时 generate_signal 返回 position=1、reason 含 golden_cross。2. 死亡交叉时返回 position=0、reason 含 death_cross。3. v2 策略在 ema_80>ema_200 且 vol_20<0.02 时返回 position=1。4. calculate_risk 返回的 stop_loss 为当前 close*(1-config 比例)。5. 与 nasdaq_v1 同参数回测结果累计收益率差异 < 2%（可后续 TASK-09 验证）。 |

---

### TASK-03: 策略工厂注册 EMA 策略

| 字段 | 内容 |
|------|------|
| **ID** | TASK-03 |
| **名称** | 策略工厂注册 EMA 策略 |
| **优先级** | P0 |
| **对应需求** | FR-V4-01 |
| **估算** | XS (0.25 天) |
| **依赖** | TASK-02 |
| **描述** | 修改 `ndx_rsi/strategy/factory.py`：在 create_strategy(strategy_name) 中增加分支，当 strategy_name 为 "EMA_cross_v1" 时返回 EMACrossoverV1Strategy(config)，为 "EMA_trend_v2" 时返回 EMATrendV2Strategy(config)。config 通过 get_strategy_config(strategy_name) 获取。 |
| **涉及文件** | `ndx_rsi/strategy/factory.py` |
| **验收标准** | 1. create_strategy("EMA_cross_v1") 返回 EMACrossoverV1Strategy 实例。2. create_strategy("EMA_trend_v2") 返回 EMATrendV2Strategy 实例。3. create_strategy("NDX_short_term") 行为不变。4. 未知策略名仍抛出 ValueError。 |

---

### TASK-04: 回测 runner 按策略预计算 EMA/vol 与预热期

| 字段 | 内容 |
|------|------|
| **ID** | TASK-04 |
| **名称** | 回测 runner 按策略预计算 EMA/vol 与预热期 |
| **优先级** | P0 |
| **对应需求** | FR-V4-01 |
| **估算** | M (1 天) |
| **依赖** | TASK-03 |
| **描述** | 修改 `ndx_rsi/backtest/runner.py`：在 preprocess 得到 df 后、创建 strategy 之后，根据 strategy_name 分支：1. **EMA_cross_v1**：若列不存在则计算 df["ema_50"]=df["close"].ewm(span=50, adjust=False).mean()，df["ema_200"]=df["close"].ewm(span=200, adjust=False).mean()（周期可从 get_strategy_config 读取）。循环起始索引设为 max(50, long_ema)，即 200，若 len(df)<200 则返回 {"error": "insufficient_data", ...}。2. **EMA_trend_v2**：计算 df["ema_80"]、df["ema_200"]、df["daily_return"]=df["close"].pct_change()、df["vol_20"]=df["daily_return"].rolling(20).std()，周期与阈值从 config 读。循环起始索引 200，不足则同上。3. **NDX_short_term**（或其它）：保持现有逻辑，循环从 50 开始，预计算 ma50/ma5/ma20/rsi/volume_ratio 不变。 |
| **涉及文件** | `ndx_rsi/backtest/runner.py` |
| **验收标准** | 1. run_backtest(strategy_name="EMA_cross_v1", ...) 不报错，且 df 含 ema_50、ema_200。2. run_backtest(strategy_name="EMA_trend_v2", ...) 不报错，且 df 含 ema_80、ema_200、vol_20。3. 数据不足 200 条时 EMA 策略返回 error。4. run_backtest(strategy_name="NDX_short_term", ...) 行为与修改前一致。 |

---

### TASK-05: 回测 runner 支持 return_series 与 series_df

| 字段 | 内容 |
|------|------|
| **ID** | TASK-05 |
| **名称** | 回测 runner 支持 return_series 与 series_df |
| **优先级** | P0 |
| **对应需求** | FR-V4-02 |
| **估算** | M (1 天) |
| **依赖** | TASK-04 |
| **描述** | 修改 `ndx_rsi/backtest/runner.py`：1. run_backtest 增加参数 return_series: bool = False。2. 当 return_series 为 True 时，在循环内维护 series_rows（list of dict），每 bar 结束后 append：date=当前日期, equity=当前权益, position=当前仓位, benchmark_cum_return=close[i]/close[loop_start], strategy_cum_return=equity（因初始 1.0）。3. 循环结束后用 pd.DataFrame(series_rows) 设 date 为 index，得到 series_df。4. 若 return_series 为 True 则返回 (result_dict, series_df)，否则仅返回 result_dict。5. 类型注解可为 Union[Dict, Tuple[Dict, pd.DataFrame]]。 |
| **涉及文件** | `ndx_rsi/backtest/runner.py` |
| **验收标准** | 1. run_backtest(..., return_series=False) 仅返回 dict，行为与现有一致。2. result, series_df = run_backtest(..., return_series=True) 得到 series_df 列含 equity、strategy_cum_return、benchmark_cum_return、position，index 为日期。3. series_df 行数 = 回测 bar 数（len(df) - loop_start）。4. (1 + result["total_return"]) 与 series_df["strategy_cum_return"].iloc[-1] 一致（允许浮点误差）。5. 对 NDX_short_term 与 EMA_cross_v1 各跑一次均满足上述。 |

---

### TASK-06: 新建 plot 模块（累计收益与多策略对比）

| 字段 | 内容 |
|------|------|
| **ID** | TASK-06 |
| **名称** | 新建 plot 模块（累计收益与多策略对比） |
| **优先级** | P1 |
| **对应需求** | FR-V4-03 |
| **估算** | M (1 天) |
| **依赖** | TASK-05 |
| **描述** | 1. 新建包 `ndx_rsi/plot/`，包含 `__init__.py` 与 `backtest_plots.py`。2. 实现 plot_cumulative_returns(series_df, *, title=None, save_path=None, show=True)：绘制 strategy_cum_return 与 benchmark_cum_return 两条曲线，图例、网格、日期轴格式与 nasdaq_v1 plot 风格对齐；save_path 非空则保存 PNG；show 为 True 则 plt.show()。3. 实现 plot_compare_strategies(series_df_by_name: Dict[str, pd.DataFrame], *, title=None, save_path=None, show=True)：在同一图上绘制基准（取首个 df 的 benchmark_cum_return 若存在）及各策略的 strategy_cum_return，图例为策略名。4. __init__.py 导出上述两函数。5. 依赖 matplotlib，无 GUI 时调用方应 show=False。 |
| **涉及文件** | `ndx_rsi/plot/__init__.py`（新建）、`ndx_rsi/plot/backtest_plots.py`（新建） |
| **验收标准** | 1. 传入符合约定的 series_df（含 strategy_cum_return、benchmark_cum_return），plot_cumulative_returns(..., show=False, save_path="/tmp/test.png") 生成文件且无报错。2. plot_compare_strategies({"A": df_a, "B": df_b}, show=False, save_path="/tmp/compare.png") 生成对比图。3. 图例与坐标轴清晰可读。 |

---

### TASK-07: CLI 增加 --plot 与 --save-plot

| 字段 | 内容 |
|------|------|
| **ID** | TASK-07 |
| **名称** | CLI 增加 --plot 与 --save-plot |
| **优先级** | P1 |
| **对应需求** | FR-V4-04 |
| **估算** | S (0.5 天) |
| **依赖** | TASK-05, TASK-06 |
| **描述** | 修改 `ndx_rsi/cli_main.py`：1. run_backtest 子命令增加可选参数 --plot（action="store_true"）与 --save-plot（type=str, default=None，表示保存路径）。2. 若存在 --plot 或 --save-plot，则调用 run_backtest(..., return_series=True)，解包得到 result 与 series_df；否则仅调用 run_backtest(...) 得到 result。3. 打印 result（与现有一致）。4. 若有 --plot，则调用 plot_cumulative_returns(series_df, title=含策略名与标的, show=True, save_path=None)。5. 若有 --save-plot PATH，则调用 plot_cumulative_returns(series_df, title=..., show=False, save_path=PATH)。6. 若仅 --save-plot 则 show=False，避免无头环境 plt.show() 报错。 |
| **涉及文件** | `ndx_rsi/cli_main.py` |
| **验收标准** | 1. python -m ndx_rsi.cli_main run_backtest --strategy EMA_cross_v1 --symbol QQQ --start 2003-01-01 --end 2025-01-01 仅打印指标，不绘图。2. 同上并加 --save-plot output/ema_v1.png 在项目下生成 output/ema_v1.png。3. 加 --plot 时弹窗显示累计收益图（若环境有 GUI）。4. 使用 NDX_short_term 时 --save-plot 同样生效。 |

---

### TASK-08: 依赖与文档更新

| 字段 | 内容 |
|------|------|
| **ID** | TASK-08 |
| **名称** | 依赖与文档更新 |
| **优先级** | P1 |
| **对应需求** | FR-V4-04, v4 技术栈 |
| **估算** | XS (0.25 天) |
| **依赖** | 无 |
| **描述** | 1. 在 `requirements.txt` 中新增一行：matplotlib>=3.7.0。2. 在 `README.md` 中补充：支持策略名 EMA_cross_v1、EMA_trend_v2；run_backtest 支持 --plot、--save-plot 示例命令与说明。 |
| **涉及文件** | `requirements.txt`、`README.md` |
| **验收标准** | 1. pip install -r requirements.txt 可安装 matplotlib。2. README 中含 EMA 策略与可视化用法说明，用户可按文档执行命令。 |

---

### TASK-09: 单测与回归验证（可选）

| 字段 | 内容 |
|------|------|
| **ID** | TASK-09 |
| **名称** | 单测与回归验证（可选） |
| **优先级** | P2 |
| **对应需求** | NFR-V4-03 |
| **估算** | M (1 天) |
| **依赖** | TASK-02, TASK-05 |
| **描述** | 1. 单测：构造带 ema_50、ema_200、close 的 DataFrame（至少 3 行），在黄金交叉、死亡交叉处断言 generate_signal 输出 position 与 reason；对 v2 构造 ema_80、ema_200、vol_20，断言 uptrend+low_vol 时 position=1。2. 回测扩展单测：对固定策略与日期区间调用 run_backtest(..., return_series=True)，断言 series_df 列存在、最后一行 strategy_cum_return 与 (1+result["total_return"]) 一致。3. 可选：与 nasdaq_v1 同参数（QQQ, 2003-2025）回测对比，EMA_cross_v1 累计收益率差异 < 2%。 |
| **涉及文件** | `tests/test_ema_strategy.py`（新建）、可选 `tests/test_backtest_series.py` |
| **验收标准** | 1. pytest tests/test_ema_strategy.py -v 通过。2. 回测 series 单测通过。3. 现有 tests/ 下用例仍通过，无回归。 |

---

## 四、任务汇总与排期

| 任务 | 优先级 | 估算 | 依赖 | 里程碑 |
|------|--------|------|------|--------|
| TASK-01 策略配置 EMA | P0 | XS | 无 | M1 |
| TASK-02 EMA 策略类 | P0 | M | T01 | M1 |
| TASK-03 工厂注册 | P0 | XS | T02 | M1 |
| TASK-04 runner 预计算 EMA/vol | P0 | M | T03 | M2 |
| TASK-05 runner return_series | P0 | M | T04 | M2 |
| TASK-06 plot 模块 | P1 | M | T05 | M3 |
| TASK-07 CLI --plot/--save-plot | P1 | S | T05,T06 | M3 |
| TASK-08 依赖与 README | P1 | XS | 无 | M4 |
| TASK-09 单测与回归 | P2 | M | T02,T05 | M4 |

**总估算**：约 5.25 天（XS=0.25d, S=0.5d, M=1d）

---

## 五、推荐实现顺序

1. **TASK-01** → **TASK-02** → **TASK-03** → **TASK-04** → **TASK-05**（配置与策略到回测扩展，串行）。
2. **TASK-08** 可与 TASK-02 并行（仅改 requirements 与 README）。
3. **TASK-06** → **TASK-07**（依赖 series_df 与 plot 模块）。
4. **TASK-09** 在 M2 完成后做，用于锁定行为与回归。

单人开发建议严格按 TASK-01 至 TASK-07 顺序执行，每完成一任务运行相关命令或单测确认后再进行下一项。

---

## 六、检查点

| 检查项 | 状态 |
|--------|------|
| 任务粒度（约 0.25～1 天） | 已确认 |
| 每任务有验收标准 | 已确认 |
| 依赖关系已识别 | 已确认 |
| 里程碑划分合理 | 已确认 |

---

**下一步**：确认任务拆分后，进入「步骤 6：代码开发」，按 TASK-01 → TASK-09 顺序实现。
