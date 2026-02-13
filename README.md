# NDX 指数回测与信号系统

纳斯达克100（QQQ）EMA 趋势策略回测与当前信号：80/200 日均线定趋势 + 20 日波动率过滤，次日执行、无 Bar 内止损止盈，输出策略与基准（买入持有）对比。

## 环境要求

- Python 3.9+
- 依赖见 `requirements.txt`（TA-Lib 可选，用于 RSI 验证）

## 安装

```bash
cd index_data_analysis
python3 -m pip install -r requirements.txt
```

若系统提示找不到 `pip`，可改用：`pip3 install -r requirements.txt`，或先创建并激活虚拟环境再安装（推荐）：

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

（可选）安装 TA-Lib 以验证手写 RSI：`conda install -c conda-forge ta-lib` 或从官方安装 C 库后 `pip install TA-Lib`。

## 配置

- `config/datasource.yaml`：数据源与标的（QQQ 等）
- `config/strategy.yaml`：
  - **backtest**：`use_stop_loss_take_profit`（默认 false）、`next_day_execution`（默认 true，T 日信号 T+1 日执行）、`commission`、`metrics.risk_free_rate` 等
  - **strategies**：当前仅保留 **EMA_trend_v2**（ema_fast=80、ema_slow=200、vol_window=20、vol_threshold=0.02）

可通过环境变量 `NDX_RSI_CONFIG` 指定 config 目录路径。

**回测逻辑**：默认次日执行、关闭 Bar 内止损/止盈，与 nasdaq_v1 等日频指数回测主流一致；输出为策略 vs 基准（买入持有）的累计收益、最大回撤、夏普对比。

## CLI 用法

在项目根目录 `index_data_analysis` 下执行（或 `PYTHONPATH=. python -m ndx_rsi.cli_main ...`）：

```bash
# 拉取数据
python -m ndx_rsi.cli_main fetch_data --symbol QQQ --start 2024-01-01 --end 2025-12-31 -o data.csv

# 回测（默认策略 EMA_trend_v2，默认区间 2003-01-01 至今日）
python -m ndx_rsi.cli_main run_backtest --symbol QQQ
python -m ndx_rsi.cli_main run_backtest --symbol QQQ --start 2002-06-15 --end 2025-12-31

# 回测并保存/显示累计收益图
python -m ndx_rsi.cli_main run_backtest --symbol QQQ --save-plot output/ema_trend_v2.png
python -m ndx_rsi.cli_main run_backtest --symbol QQQ --plot

# 生成当前信号（可读报告：收盘价、EMA、波动率、推导逻辑、操作建议、止损止盈）
python -m ndx_rsi.cli_main run_signal --symbol QQQ
# run_signal 会拉取约 400 日历史以计算 EMA200，再输出最新一根 K 线的信号报告

# 验证 RSI 手写与 TA-Lib 一致性（可选）
python -m ndx_rsi.cli_main verify_indicators --symbol QQQ --start 2024-01-01 --end 2025-12-31
```

## 测试

```bash
cd index_data_analysis
pytest tests/ -v
pytest tests/ --cov=ndx_rsi --cov-report=term-missing  # 覆盖率
```

## 文档

- **v1**：`docs/v1/`（需求、技术设计、开发任务拆分等）
- **v2**：`docs/v2/`（回测设计、绩效指标、回撤熔断等）
- **v4**：`docs/v4/`（EMA 策略、回测序列与可视化、空仓无风险利率计息 06-backtest-cash-risk-free-accrual）
- **v5**：`docs/v5/`（信号可读化与推导逻辑展示、run_signal 报告格式）

当前策略仅保留 **EMA_trend_v2**（80/200 EMA + 波动率过滤），配置见 `config/strategy.yaml` 的 `strategies.EMA_trend_v2`。

## 免责声明

本系统仅供学习与研究，不构成任何投资建议；实盘交易需自行合规并承担风险。
