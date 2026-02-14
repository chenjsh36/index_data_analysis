# 技术方案设计（TDD）— v6

**文档类型**：技术设计（步骤 4）  
**依据**：`02-requirements-documentation.md`、`03-technology-stack-selection.md`  
**参考规范**：C4 简化、分层架构、设计系统引用、先简单实现

---

## 1. 系统架构概览

### 1.1 C4 语境（Context）

```
                    +------------------+
                    |  用户 / 读者      |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                                       |
         v                                       v
+----------------+                    +------------------+
| GitHub Actions |                    | 浏览器            |
| (定时/手动)     |                    | 访问静态页         |
+--------+-------+                    +--------+---------+
         |                                       |
         v                                       v
+----------------+                    +------------------+
| index_data_    |                    | 静态站点          |
| analysis 仓库  |--------------------| (HTML+JS+JSON)    |
| run_signal +   | 产出 JSON/报告     | 走势图+信号展示    |
| 通知脚本       |                    |                   |
+----------------+                    +------------------+
```

- **左侧**：定时或手动触发 GitHub Actions → 在仓库内执行跑信号 → 将报告发送至邮件/钉钉。
- **右侧**：静态站点由本仓库提供（预生成 JSON + HTML/JS），用户用浏览器打开页面查看 5 年走势与当日信号。

### 1.2 模块划分（简化）

| 模块 | 路径/形式 | 职责 |
|------|-----------|------|
| 定时与执行 | `.github/workflows/daily_signal.yml` | 定时触发、安装依赖、执行跑信号与通知 |
| 跑信号 | 现有 `ndx_rsi.cli_main run_signal` | 拉数据、算指标、生成信号与可读报告（不变） |
| 通知 | 新增 `scripts/run_signal_and_notify.py` 或 `ndx_rsi/notify.py` | 调用 run_signal、捕获报告文本、按 Secrets 发邮件与钉钉 Webhook |
| 静态数据生成 | 新增 `scripts/generate_static_data.py` 或 CLI 子命令 | 拉 5 年数据写 `timeseries.json`、跑一次 signal 写 `signal.json` |
| 静态站点 | 新增 `web/` 或 `static/` | `index.html` + CSS + JS，用 ECharts 画走势图、展示 signal.json；启动方式为 `python -m http.server` 或文档说明 |

---

## 2. 数据流与时序

### 2.1 每日定时：跑信号 + 推送

```
  cron / workflow_dispatch
         |
         v
  +------+------+
  | checkout    |
  | setup-python|
  | pip install |
  +------+------+
         |
         v
  +------+------+
  | run_signal  |  (python -m ndx_rsi.cli_main run_signal --symbol QQQ)
  | 或内嵌调用   |  -> 得到 report: str
  +------+------+
         |
         v
  +------+------+
  | notify      |  if EMAIL_*: SMTP 发邮件，正文 = report
  |             |  if CUSTOM_WEBHOOK_URLS: 对每个 URL POST（钉钉格式：{"msgtype":"text","text":{"content": report}}）
  +------+------+
         |
         v
  （可选）写 signal.json 到 web/ 或 static/ 目录，便于静态页展示“最近一次”
```

- 与 **daily_stock_analysis** 对齐：Secrets 使用 `EMAIL_SENDER`、`EMAIL_PASSWORD`、`EMAIL_RECEIVERS`、`CUSTOM_WEBHOOK_URLS`（钉钉多 URL 逗号分隔）。
- 先简单实现：通知脚本仅支持“文本正文”推送；邮件用纯文本或简单 HTML，钉钉用 `text` 类型即可。

### 2.2 静态页数据更新与访问

```
  （定时任务同一 workflow 或单独 step）
         |
         v
  +------+------+
  | 拉 5 年 QQQ  |  fetch_data / 现有 data 模块，end=today, start=today-5y
  | 写 timeseries.json
  +------+------+
         |
         v
  +------+------+
  | 跑一次 signal|  同 run_signal，结果序列化
  | 写 signal.json
  +------+------+
         |
         v
  web/series.json, web/signal.json  (或 static/ 下)
         |
         v
  用户打开 index.html -> JS fetch series.json + signal.json -> ECharts 绘图 + 渲染信号卡片
```

- 静态页**不**请求后端 API，只加载同源或约定路径下的 JSON 文件。

---

## 3. 数据与“接口”约定

### 3.1 无 REST API

- 本期不做实时后端；所有对前端的“接口”均为**静态 JSON 文件**。

### 3.2 预生成 JSON 格式（先简单实现）

**timeseries.json**（5 年走势，供 ECharts 折线图）

```json
{
  "symbol": "QQQ",
  "from": "2020-02-13",
  "to": "2025-02-13",
  "series": [
    ["2020-02-13", 218.5],
    ["2020-02-14", 219.1]
  ]
}
```

- `series`：`[date_str, close]` 数组，按日升序；与现有 `ndx_rsi` 数据源一致（yfinance 日频 close）。

**signal.json**（最近一次 run_signal 结果，供页面“当日信号”区块）

```json
{
  "date": "2025-02-13",
  "symbol": "QQQ",
  "strategy": "EMA_trend_v2",
  "close": 485.2,
  "ema_fast": 480.1,
  "ema_slow": 472.3,
  "vol_20": 0.015,
  "derivation": "EMA80(480.1) > EMA200(472.3) → 上升趋势；vol_20(0.015) < 0.02 → 低波动；→ 满仓持有",
  "action": "满仓持有",
  "stop_loss": null,
  "take_profit": null
}
```

- 字段与现有 `format_signal_report`（EMA_trend_v2）一致，便于从现有 `sig`、`risk`、`row` 序列化生成；若后续策略扩展，可加可选字段。

### 3.3 报告文本（推送用）

- 邮件正文、钉钉 Webhook 的 `content`：直接使用现有 `format_signal_report(...)` 返回的字符串，无需新格式。

---

## 4. 部署与运行方式

### 4.1 GitHub Actions

- **工作流文件**：`.github/workflows/daily_signal.yml`。
- **触发**：`schedule`（如每日 UTC 对应收盘后时间，与 daily_stock_analysis 类似）、`workflow_dispatch` 手动。
- **步骤**：checkout → setup-python 3.9+ → pip install -r requirements.txt → 运行“跑信号 + 通知”脚本（传入 env：EMAIL_*、CUSTOM_WEBHOOK_URLS、可选 SYMBOL）。
- **可选**：同 workflow 中增加“生成 timeseries.json + signal.json 并 commit 到仓库或 upload-artifact”，供静态页使用；先简单实现可仅“跑信号+推送”，静态数据本地或单独 job 生成。

### 4.2 静态站点

- **开发/本地**：在 `index_data_analysis` 根目录或 `web/` 下执行 `python -m http.server 8080`，浏览器访问 `http://localhost:8080`（或对应路径）。
- **生产**：可将 `web/`（或 `static/`）部署到 GitHub Pages 或任意静态托管；JSON 由定时任务或本地脚本生成后放入同一目录或约定路径。

---

## 5. 前端/界面设计约束（引用设计系统）

- 本项目涉及 **Web 端静态页面**，实现须符合步骤 3 产出的设计系统。
- **设计系统引用**：`design-system/指数数据与信号展示/MASTER.md`（项目根为 `index_data_analysis` 时的相对路径）。
  - **风格**：Glassmorphism（毛玻璃、层次感）。
  - **色彩**：Primary `#2563EB`、Secondary `#3B82F6`、CTA `#F97316`、Background `#F8FAFC`、Text `#1E293B`（见 MASTER 中 CSS 变量与组件规范）。
  - **字体**：Inter（标题与正文）。
  - **组件与交互**：按钮、卡片、间距、阴影、焦点与无障碍、响应式断点等以 MASTER 为准；图标使用 SVG（如 Heroicons/Lucide），禁止用 emoji 作图标。
- **图表**：先简单实现采用 **ECharts**（CDN 引入），单折线图展示 5 年 close 走势；后续可再考虑 Lightweight Charts 等。
- **页面结构**：先简单实现单页：上方或左侧为 5 年走势图，下方或右侧为“当日信号”卡片（展示 signal.json 的 close、EMA、波动率、推导逻辑、操作建议等），符合 MASTER 的 Hero + Features 式分区即可，不强制多页。

---

## 6. 风险与简化说明

| 项 | 说明 |
|----|------|
| 通知实现 | 先不复用 daily_stock_analysis 的整包，在本仓库内实现最小可用的邮件 SMTP + 钉钉 Webhook POST，减少依赖与复杂度。 |
| 静态数据更新 | 若 Actions 不直接写回仓库，则“最近一次”信号与 5 年数据可在本地或自建 runner 上生成后手动放入 `web/`，或后续再加“生成并 commit”步骤。 |
| 图表库 | 先固定 ECharts，避免同时维护两套图表实现。 |

---

## 7. 输出物与检查点

| 输出物 | 状态 |
|--------|------|
| 技术设计文档（本文档） | ✅ |
| 系统架构与数据流（C4 简化 + 时序） | ✅ 第 1、2 节 |
| 数据/接口约定（静态 JSON 格式） | ✅ 第 3 节 |
| 部署与运行方式 | ✅ 第 4 节 |
| 前端设计约束（引用 design-system/MASTER.md） | ✅ 第 5 节 |
| 文件名 | `04-technical-design.md`（本文档） |

- ✅ 先简单实现：单 workflow、单通知脚本、单页静态站 + 预生成 JSON、ECharts 单图。
- ✅ 未设计数据库与 REST API，符合“静态 + 预生成”的约束。
- ✅ UI 实现约束已明确引用设计系统，供步骤 5（开发任务拆分）与步骤 6（代码开发）使用。

**下一步**：完成本步骤后需用户确认；确认后进入步骤 5「开发步骤拆分」。
