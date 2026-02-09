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
- `config/strategy.yaml`：策略参数（RSI 周期、阈值、风控）

可通过环境变量 `NDX_RSI_CONFIG` 指定 config 目录路径。

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

- 需求与设计见 `docs/v1/`：01-requirements_gathering 至 05-development-task-breakdown
- 技术方案见 `docs/v1/04-technical-design.md`

## 免责声明

本系统仅供学习与研究，不构成任何投资建议；实盘交易需自行合规并承担风险。
