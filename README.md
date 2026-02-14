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

## v6：每日信号推送与静态页

- **定时跑信号并推送**：在 GitHub 上配置 Secrets 后，可用 Actions 每日自动跑信号并发送到邮件、钉钉。
  - 工作流：`.github/workflows/daily_signal.yml`（定时 + 手动触发）。
  - Secrets：`EMAIL_SENDER`、`EMAIL_PASSWORD`、`EMAIL_RECEIVERS`（邮件）；`CUSTOM_WEBHOOK_URLS`（钉钉等 Webhook，逗号分隔）；可选 `SYMBOL`、`STRATEGY`。
  - 本地测试推送：`PYTHONPATH=. python scripts/run_signal_and_notify.py`（需配置上述环境变量）。
- **静态页**：在仓库内生成 5 年走势与当日信号 JSON 后，用浏览器打开页面查看。
  - 生成数据：`PYTHONPATH=. python scripts/generate_static_data.py --out-dir web`
  - 启动服务：`cd web && python3 -m http.server 8080`，访问 `http://localhost:8080`
  - 页面会加载 `web/timeseries.json` 与 `web/signal.json`（ECharts 走势图 + 信号卡片）。

**GitHub 仓库配置**：启用 Actions、配置 Secrets（邮件/钉钉）等步骤见 [docs/v6/setup-github.md](docs/v6/setup-github.md)。  
详见 `docs/v6/`（需求、技术方案、任务拆分与实现说明）。

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
- **v6**：`docs/v6/`（每日信号推送、静态页、GitHub Actions、设计系统）

当前策略仅保留 **EMA_trend_v2**（80/200 EMA + 波动率过滤），配置见 `config/strategy.yaml` 的 `strategies.EMA_trend_v2`。

## 免责声明

本系统仅供学习与研究，不构成任何投资建议；实盘交易需自行合规并承担风险。
