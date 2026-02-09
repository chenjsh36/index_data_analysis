# 技术方案设计文档（Technical Design Document, TDD）

**文档版本**：1.0  
**产出日期**：2026-02-08  
**依据**：研发流程步骤 4 - 技术方案设计  
**上游输入**：`02-requirements-documentation.md`、`03-technology-stack-selection.md`、`design.md`、`tech_v1.md`、`tech_v2.md`

---

## 1. 系统架构

### 1.1 整体架构图（分层 + 接口抽象）

采用分层架构 + 接口抽象，与 tech_v1/v2、步骤 3 技术栈一致。首版以单进程运行，数据与策略通过接口扩展。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           入口层（CLI / 可选 REST）                          │
│  run_backtest / run_signal / fetch_data 等命令或 API                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            策略层（Strategy）                                │
│  BaseTradingStrategy ← NDXShortTermRSIStrategy                               │
│  StrategyFactory.create_strategy(name)                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            信号层（Signal）                                  │
│  趋势判定 / 量能验证 / RSI 信号（超买超卖、背离、金叉死叉）/ 组合过滤         │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            计算层（Indicator）                              │
│  手写 RSI/MA/量能比 + TA-Lib 验证；市场环境识别；阈值表                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            数据层（Data）                                    │
│  BaseDataSource ← YFinanceDataSource；预处理（前复权、缺失值、量能标准化）   │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
┌─────────────────────────────────────────────────────────────────────────────┐
│                            配置层（Config）                                  │
│  config/datasource.yaml、config/strategy.yaml（PyYAML 加载）                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  回测层      │  │  风控层      │  │  持久化(可选) │  │  监控(可选)   │
│  Backtrader  │  │  仓位/止损   │  │  SQLite      │  │  告警/日志    │
│  或自研循环  │  │  极端行情    │  │              │  │              │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

### 1.2 C4 上下文与容器（简化）

- **System**：NDX RSI 量化分析与交易信号系统  
- **Users**：交易者（查看信号/回测结果）、策略开发（运行回测/调参）、运维（监控与告警）  
- **External**：Yahoo Finance（yfinance）、可选 VIX 数据源、可选钉钉/邮件告警  

**容器（Containers）**：

| 容器 | 职责 |
|------|------|
| 核心应用（Python 进程） | 数据拉取、指标计算、信号生成、回测、风控、配置加载 |
| 可选：SQLite 文件 | 历史行情缓存、回测结果存储 |
| 可选：监控/告警 | 定时任务 + 告警渠道（步骤 5/6 细化） |

---

## 2. 模块划分与接口规范

### 2.1 数据层：BaseDataSource

**职责**：按标的与时间范围获取行情（OHLCV），屏蔽具体数据源。

**接口定义**（与 tech_v2 对齐）：

```python
from abc import ABC, abstractmethod
import pandas as pd
from typing import Optional

class BaseDataSource(ABC):
    def __init__(self, index_code: str, config: dict): ...

    @abstractmethod
    def get_historical_data(
        self,
        start_date: str,
        end_date: str,
        frequency: str = "1d"
    ) -> pd.DataFrame:
        """返回 DataFrame，列至少含：open, high, low, close, volume；索引为 DatetimeIndex。"""
        pass

    @abstractmethod
    def get_realtime_data(self) -> pd.DataFrame:
        """获取最新一段数据（用于信号生成）。"""
        pass
```

**实现**：`YFinanceDataSource` 使用 yfinance，列名统一为小写（open/high/low/close/volume），并做前复权与基本缺失处理（见 2.5 数据预处理）。

**配置**：`config/datasource.yaml` 中按 index_code 配置 code、ticker、data_source、frequency、fields。

---

### 2.2 计算层：指标与验证

**职责**：计算 RSI、MA50、20 日均量、量能比；市场环境识别；手写与 TA-Lib 双路径验证。

**核心接口/函数**：

| 名称 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `calculate_rsi_handwrite(prices, period)` | Series, int | Series | 手写 RSI，与 BRD 公式一致 |
| `calculate_rsi_talib(prices, period)` | Series, int | Series | TA-Lib 结果，用于验证 |
| `verify_rsi(prices, period, max_diff=0.1)` | Series, int, float | bool | 手写 vs TA-Lib 偏差≤max_diff |
| `calculate_ma(series, window)` | Series, int | Series | 简单移动平均（MA50、20 日均量） |
| `calculate_volume_ratio(volume, window=20)` | Series, int | Series | 当日量 / 20 日均量 |
| `judge_market_env(prices, ma50)` | Series, Series | str | "bull" \| "bear" \| "oscillate" \| "transition" |
| `get_rsi_thresholds(market_env)` | str | dict | 超买/超卖/强超买/强超卖阈值 |

**数据流**：原始 close/volume → 手写 RSI/MA/量能比 → 与 TA-Lib 比对（RSI）→ 供信号层使用。

---

### 2.3 信号层：规则与组合

**职责**：趋势判定、量能验证、RSI 信号（超买超卖、顶/底背离、金叉/死叉）及组合过滤（趋势 > 量能 > RSI）。

**规则模块**（与 design.md 一致）：

- **趋势规则**：50 日均线斜率 + 连续 2 日收盘价与 MA50 关系 → 上升/下降/震荡。
- **量能规则**：放量 ≥1.2、缩量 ≤0.8、巨量 ≥1.5、地量 ≤0.5（相对 20 日均量）。
- **RSI 规则**：按市场环境取阈值；背离需价格高低点 + RSI 高低点 + 量能条件；金叉/死叉需交叉区间 + 量能 + 均线条件。
- **组合**：先判定趋势与量能，再应用 RSI 信号；上升趋势忽略单纯超买（除非缩量滞涨），下降趋势忽略单纯超卖（除非缩量企稳）。

**输出**：信号类型（buy/sell/hold/buy_light/sell_light）、建议仓位比例、触发原因（如 golden_cross、oversell 等）。

---

### 2.4 策略层：BaseTradingStrategy

**职责**：封装「数据 + 计算 + 信号 + 风控」，对外提供 `generate_signal` 与 `calculate_risk`。

**接口定义**（与 tech_v2 对齐）：

```python
from abc import ABC, abstractmethod
import pandas as pd
from typing import Any

class BaseTradingStrategy(ABC):
    def __init__(self, strategy_config: dict): ...

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> dict:
        """
        输入：含 close, volume, rsi_short, rsi_long, ma50, volume_ratio 等列的 DataFrame（最新为 iloc[-1]）。
        输出：{"signal": str, "position": float, "reason": str, ...}，可选 stop_loss/take_profit。
        """
        pass

    @abstractmethod
    def calculate_risk(self, signal: dict, data: pd.DataFrame) -> dict:
        """返回 {"stop_loss": float, "take_profit": float} 等。"""
        pass
```

**实现**：`NDXShortTermRSIStrategy` 从 strategy_config 读取 RSI 周期、阈值、风控参数；内部调用信号层与风控规则，返回信号与止损止盈。

**工厂**：`StrategyFactory.create_strategy(strategy_name: str) -> BaseTradingStrategy`，从 `config/strategy.yaml` 加载配置并实例化对应策略类。

---

### 2.5 风控层

**职责**：仓位上限（按市场环境）、止损止盈比例、极端行情禁止（VIX>30 且 RSI 极值）、回撤熔断（累计回撤≥10% 降仓并暂停）。

**集成方式**：策略在 `generate_signal` 前先做风控检查（极端行情不输出开仓）；`calculate_risk` 中根据标的类型（ETF/杠杆 ETF）与策略配置返回止损止盈；回测引擎按日检查回撤并应用熔断规则。

---

### 2.6 回测层

**职责**：在历史区间内按日（或 Bar）推进，调用策略生成信号与风控，模拟成交，统计绩效。

**方案**：首选 **Backtrader**；策略封装为 Backtrader 的 Strategy 子类，在 `next()` 中调用本项目的信号层/策略层逻辑（或直接复用 `NDXShortTermRSIStrategy.generate_signal` 的输入构造）。  
**输出**：胜率、盈亏比、最大回撤、年化收益、夏普比率等；可选写入 SQLite（见 3）。

**备选**：若回测性能成为瓶颈，可评估 **VectorBT** 或自研向量化回测循环，接口保持「输入 DataFrame + 策略名 → 输出绩效 dict」。

---

### 2.7 数据预处理（数据层内）

- **前复权**：yfinance 若提供 Adj Close，优先用 Adj Close 作为 close；否则保持 close，并在文档中说明限制。
- **缺失值**：日线缺失超 2 个周期则标记异常，信号模块可据此暂停输出；分钟级用前周期填充（若实现分钟级）。
- **量能标准化**：volume_ratio = volume / volume.rolling(20).mean()；比值 >3 视为异常，可替换为 1 或截断。
- **列名**：统一小写，与 config 中 fields 一致：open, high, low, close, volume。

---

## 3. 数据模型与存储

### 3.1 内存数据结构（DataFrame 约定）

**行情 DataFrame**（数据层输出 / 策略输入）：

| 列名 | 类型 | 说明 |
|------|------|------|
| open, high, low, close, volume | float | 必选 |
| ma50 | float | 计算层填充 |
| rsi_9, rsi_24 | float | 计算层填充（列名可配置） |
| volume_ratio | float | 计算层填充 |
| market_env | str | 可选，计算层填充 |

索引：`DatetimeIndex`，按时间升序。

**信号/决策 dict**（策略输出）：

```python
{
    "signal": "buy" | "sell" | "hold" | "buy_light" | "sell_light",
    "position": float,  # 0~1 或 -1~0
    "reason": str,      # 如 "golden_cross", "oversell"
    "stop_loss": float | None,
    "take_profit": float | None,
    "ts": str | None    # 信号时间，ISO 格式
}
```

---

### 3.2 持久化（可选）：SQLite

首版若需缓存历史数据或回测结果，可采用 SQLite。以下为建议表结构，非强制首版实现。

**表：ohlcv_cache**

| 列 | 类型 | 说明 |
|----|------|------|
| symbol | TEXT | 如 QQQ, ^NDX |
| frequency | TEXT | 1d, 30m |
| ts | TEXT | 日期/时间 ISO |
| open, high, low, close, volume | REAL | 行情 |
| PRIMARY KEY (symbol, frequency, ts) | | |

**表：backtest_runs**

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | 自增 |
| strategy_name | TEXT | 如 NDX_short_term |
| symbol | TEXT | 如 QQQ |
| start_date, end_date | TEXT | 回测区间 |
| win_rate, profit_factor, max_drawdown, sharpe | REAL | 绩效 |
| created_at | TEXT | ISO |

**表：signals_log**（可选，用于复盘）

| 列 | 类型 | 说明 |
|----|------|------|
| id | INTEGER PK | |
| strategy_name | TEXT | |
| ts | TEXT | 信号时间 |
| signal | TEXT | buy/sell/hold 等 |
| position | REAL | |
| reason | TEXT | |
| stop_loss, take_profit | REAL | 可选 |

索引建议：`ohlcv_cache(symbol, frequency, ts)`；`backtest_runs(strategy_name, created_at)`。

---

## 4. API 设计

首版以 **CLI 入口** 为主，便于本地回测与信号生成。若后续提供 REST，可采用以下约定。

### 4.1 CLI 入口（首版）

| 命令/脚本 | 说明 | 典型参数 |
|-----------|------|----------|
| `fetch_data` | 拉取并可选落库 | --symbol, --start, --end, --frequency |
| `run_backtest` | 执行回测并输出绩效 | --strategy, --symbol, --start, --end |
| `run_signal` | 对最新数据生成信号 | --strategy, --symbol |
| `verify_indicators` | 运行 RSI/MA 手写 vs TA-Lib 验证 | --symbol, --start, --end |

（具体命令名与参数在步骤 5 拆分为开发任务时可再定。）

### 4.2 可选 REST API（后续）

若在步骤 5/6 中实现 HTTP 服务，建议至少提供：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/signal | 查询当前信号；query: strategy, symbol |
| POST | /api/v1/backtest | 提交回测；body: strategy, symbol, start_date, end_date |
| GET | /api/v1/backtest/{run_id} | 查询回测结果 |

**响应格式**（统一封装）：

```json
{
  "success": true,
  "data": { ... },
  "error": null
}
```

**错误**：HTTP 4xx/5xx，body 中 `success: false`, `error: { "code": "...", "message": "..." }`。

（OpenAPI/Swagger 可在实现阶段补充。）

---

## 5. 数据流图

```
[ 数据源 yfinance ] → get_historical_data / get_realtime_data
        ↓
[ 预处理 ] 前复权、缺失处理、量能比
        ↓
[ 计算层 ] RSI(9/24)、MA50、volume_ratio、market_env、thresholds
        ↓
[ 信号层 ] 趋势 + 量能 + RSI 规则 → 信号类型 + 仓位 + 原因
        ↓
[ 风控层 ] 极端行情/回撤检查；止损止盈计算
        ↓
[ 策略输出 ] signal dict → CLI 输出 / 回测引擎 / 可选 API
        ↓
[ 回测 ] 按 Bar 推进 → 模拟仓位与成交 → 绩效统计 → 报表/持久化
```

---

## 6. 关键业务流程时序

### 6.1 回测流程

```
用户/CLI          数据层           计算层           策略层           回测引擎
   |                |                |                |                |
   | run_backtest   |                |                |                |
   |--------------->|                |                |                |
   |                | get_historical |                |                |
   |                |-------------->| (内部)          |                |
   |                |<--------------|                |                |
   |                | 返回 DataFrame |                |                |
   |                |-------------------------------->|                |
   |                |                | 预计算指标      |                |
   |                |                |<---------------|                |
   |                |                |--------------->|                |
   |                |                |                | 按 Bar 循环     |
   |                |                |                | generate_signal |
   |                |                |                | calculate_risk |
   |                |                |                |---------------->|
   |                |                |                | 成交/仓位更新   |
   |                |                |                |<----------------|
   |                |                |                | ...             |
   |                |                |                | 绩效统计        |
   |<------------------------------------------------------------------|
   | 返回报表/文件   |                |                |                |
```

### 6.2 实时信号生成流程

```
定时任务/CLI    数据层           计算层           策略层           风控层
   |              |                |                |                |
   | run_signal   |                |                |                |
   |------------->|                |                |                |
   |              | get_realtime   |                |                |
   |              |-------------->| (内部)          |                |
   |              |<--------------|                |                |
   |              | 返回 DataFrame |                |                |
   |              |------------------------------->|                |
   |              |                |                | generate_signal|
   |              |                |                |--------------->|
   |              |                |                | 极端行情检查    |
   |              |                |                |<---------------|
   |              |                |                | calculate_risk |
   |              |                |                | 输出 signal dict|
   |<------------------------------------------------|                |
   | 日志/告警/API |                |                |                |
```

---

## 7. 部署架构

### 7.1 首版：单机本地

- **运行方式**：Python 3.9+ 虚拟环境（venv/conda），依赖见 `03-technology-stack-selection.md`。
- **配置**：项目内 `config/datasource.yaml`、`config/strategy.yaml`；可通过环境变量覆盖配置路径（可选）。
- **执行**：CLI 脚本或 `python -m` 入口；无常驻服务时无需进程管理。

### 7.2 可选：Docker

- **镜像**：基于 `python:3.11-slim`，安装 TA-Lib 依赖（或使用带 TA-Lib 的镜像），COPY 代码与 config，`pip install -r requirements.txt`。
- **运行**：容器内执行 `run_backtest` / `run_signal`；若需定时任务，可在容器内使用 cron 或 APScheduler，或由宿主机 cron 调 `docker run`。
- **数据**：若使用 SQLite，可将数据库文件挂载为 volume，便于持久化。

### 7.3 环境与依赖

- **Python**：3.9+（建议 3.11）。
- **系统依赖**：TA-Lib 的 C 库（或通过 conda 安装）。
- **敏感信息**：若后续接入付费数据源或告警渠道，API Key 等通过环境变量或密钥管理注入，不写入配置文件。

---

## 8. 技术风险与缓解

| 风险 | 缓解 |
|------|------|
| TA-Lib 安装困难 | 提供 conda 安装说明；或短期用 pandas-ta 等纯 Python 库做验证替代。 |
| yfinance 限流/变更 | 数据源抽象，可替换为其他实现；请求限速与重试。 |
| 回测与实盘差异 | 回测中显式加入手续费、滑点；文档标明「仅供研究、不构成实盘建议」。 |
| 配置错误导致错误信号 | 配置加载时做 schema 校验；关键参数范围检查。 |

---

## 9. 与需求/上游文档的对应

| 需求/文档 | 本设计对应 |
|-----------|------------|
| FR-01 数据获取与预处理 | 2.1 BaseDataSource、2.7 预处理 |
| FR-02 指标计算 | 2.2 计算层、手写+TA-Lib 验证 |
| FR-03 市场环境与阈值 | 2.2 judge_market_env、get_rsi_thresholds |
| FR-04 信号与过滤 | 2.3 信号层 |
| FR-05 信号与风控输出 | 2.4 策略层、2.5 风控层、3.1 signal dict |
| FR-06 回测 | 2.6 回测层、6.1 时序 |
| FR-08 配置化 | 2.4 StrategyFactory、config/*.yaml |
| FR-11 极端行情/回撤 | 2.5 风控层 |
| 03 技术栈 | Python/pandas/yfinance/TA-Lib/Backtrader/YAML/pytest/SQLite/Docker |
| design.md / tech_v1/v2 | 分层、接口、YAML、策略工厂、手写验证 |

---

## 10. 前端/UI 设计约束（可选）

本项目首版以**后端与回测**为主，无可视化界面。若在步骤 5/6 中实现 **Web 可视化**（FR-10）：

- 应在实现阶段选定前端技术栈（见 03-technology-stack-selection），并**调用 ui-ux-pro-max** 生成设计系统（如 `design-system/MASTER.md`）。
- 技术方案与代码中须**引用该设计系统**，明确色彩、字体、组件、响应式与无障碍要求，保证 UI 与设计系统一致。
- 本 TDD 不包含具体页面线框图；待确定做可视化后再补充「前端模块设计」小节。

---

## 11. 输出物清单

| 输出物 | 状态 |
|--------|------|
| 技术设计文档（TDD） | ✅ 本文档 |
| 系统架构图（分层 + 接口） | ✅ 1.1、1.2 |
| 模块划分与接口规范 | ✅ 第 2 节 |
| 数据模型与存储设计 | ✅ 第 3 节 |
| API 设计（CLI + 可选 REST） | ✅ 第 4 节 |
| 数据流图 | ✅ 第 5 节 |
| 时序图（回测、信号生成） | ✅ 第 6 节 |
| 部署架构 | ✅ 第 7 节 |
| 前端设计约束说明 | ✅ 第 10 节（引用设计系统，待实现时生成） |

---

**下一步**：确认技术方案后，进入「步骤 5：开发步骤拆分」。如需调整架构或接口，可直接指出。
