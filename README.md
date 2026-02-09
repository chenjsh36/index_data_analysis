# NDX RSI 量化分析与交易信号系统

纳斯达克100（NDX/QQQ/TQQQ）短线波段 RSI 策略：实现「50日均线定趋势 + 成交量验真假 + RSI找点位」的闭环。

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

- `config/datasource.yaml`：数据源与标的（NDX/QQQ/TQQQ）
- `config/strategy.yaml`：策略参数（RSI 周期、阈值、风控）、**v2 回测配置**（`backtest` 段：止损止盈开关、趋势破位、回撤熔断、无风险利率）、**v2 背离开关**（`use_divergence`）

可通过环境变量 `NDX_RSI_CONFIG` 指定 config 目录路径。

**v2 回测**：回测时默认启用 Bar 内止损/止盈，绩效指标为标准口径（profit_factor = 总盈利/总亏损，夏普 = (年化收益 - 无风险)/收益标准差）。在 `strategy.yaml` 的 `backtest` 下可关闭 `use_stop_loss_take_profit` 以对比「仅信号平仓」结果。

## CLI 用法

在项目根目录 `index_data_analysis` 下执行（或 `PYTHONPATH=. python -m ndx_rsi.cli_main ...`）：

```bash
# 拉取数据
python -m ndx_rsi.cli_main fetch_data --symbol QQQ --start 2024-01-01 --end 2026-02-09 -o data.csv

# 回测
python -m ndx_rsi.cli_main run_backtest --strategy NDX_short_term --symbol QQQ --start 2018-01-01 --end 2025-12-31

# 生成当前信号
python -m ndx_rsi.cli_main run_signal --strategy NDX_short_term --symbol QQQ

# 验证 RSI 手写与 TA-Lib 一致性
python -m ndx_rsi.cli_main verify_indicators --symbol QQQ --start 2024-01-01 --end 2025-02-09
```

## 测试

```bash
cd index_data_analysis
pytest tests/ -v
pytest tests/ --cov=ndx_rsi --cov-report=term-missing  # 覆盖率
```

## 文档

- **v1**：`docs/v1/`（01-requirements_gathering 至 06-code-development、07-simplifications-and-backtest-impact）
- **v2**：`docs/v2/`（01-requirements_gathering、04-technical-design、05-development-task-breakdown、06-code-development）；v2 在 v1 基础上增加回测止损止盈、连续 2 日市场环境、标准绩效指标、回撤熔断与可选背离

## 免责声明

本系统仅供学习与研究，不构成任何投资建议；实盘交易需自行合规并承担风险。
