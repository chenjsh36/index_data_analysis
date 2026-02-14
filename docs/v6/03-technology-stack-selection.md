# 技术栈选型（步骤 3）— v6

**文档类型**：技术栈选择  
**依据**：`02-requirements-documentation.md`、参考项目 `daily_stock_analysis`  
**参考规范**：技术选型评估矩阵、FURPS+、设计系统（ui-ux-pro-max）

---

## 1. 选型总览

| 能力域 | 选型结论 | 说明 |
|--------|----------|------|
| 定时执行与推送 | **GitHub Actions** + **Python（现有）** + **Secrets（邮件/钉钉）** | 与 daily_stock_analysis 一致，零服务器成本 |
| 静态站点 | **HTML + CSS + JS（原生/轻量）** + **图表库** | 无构建框架，预生成数据 + 静态资源即可 |
| 数据与报告生成 | **现有 Python 管道**（run_signal、fetch_data）+ **预生成 JSON/HTML** | 与现有 ndx_rsi 一致，定时任务产出供前端展示 |
| 设计系统 | **ui-ux-pro-max 生成**（Glassmorphism + Inter） | 见下文及 `design-system/指数数据与信号展示/MASTER.md` |

---

## 2. 技术栈明细与评估

### 2.1 定时跑信号与推送

| 技术项 | 选型 | 评估维度 | 说明 |
|--------|------|----------|------|
| 调度与运行环境 | **GitHub Actions** | 成熟度、成本、可维护性 | 与 daily_stock_analysis 一致；cron 定时 + workflow_dispatch 手动；无需自建服务器 |
| 运行时 | **Python 3.9+**（现有） | 兼容性、生态 | 沿用项目现有 Python 与 `ndx_rsi.cli_main run_signal`，无新增语言 |
| 依赖安装 | **pip + requirements.txt** | 可复现 | 与现有项目一致；Actions 中 checkout → setup-python → pip install -r requirements.txt |
| 通知渠道 | **Secrets：邮件（EMAIL_*）、钉钉（CUSTOM_WEBHOOK_URLS）** | 与需求一致 | 参考 daily_stock_analysis 的 Secrets 命名与用法；钉钉使用自定义 Webhook，多 URL 逗号分隔 |

**参考实现**：`daily_stock_analysis/.github/workflows/daily_analysis.yml`（schedule、env、run 步骤）。

### 2.2 静态站点（走势图 + 当日信号）

| 技术项 | 选型 | 评估维度 | 说明 |
|--------|------|----------|------|
| 页面技术 | **HTML5 + CSS3 + JavaScript（原生或轻量）** | 学习成本、部署简单度 | 无需 React/Vue 构建；静态文件即可，便于“本仓库启动静态服务” |
| 图表库 | **ECharts** 或 **Lightweight Charts** | 成熟度、金融时间序列、体积 | 二选一：ECharts 生态好、文档全；Lightweight Charts 专为 K 线/时序设计、体量小。技术方案阶段定其一 |
| 静态服务 | **Python `http.server`** 或 **Node `serve`** | 零配置、本仓库可执行 | 开发与本地展示用；生产可为 GitHub Pages / 任意静态托管 |
| 数据来源 | **预生成 JSON + 可选预渲染 HTML 片段** | 与需求“预生成”一致 | 定时任务（或与 run_signal 同一 workflow）产出：5 年走势数据 JSON、最新信号结果 JSON；前端 fetch 展示 |

**不选用**：重型前端框架（React/Vue 全家桶）、实时后端 API（本期不做）、服务端模板引擎（可选后续若需服务端渲染再考虑）。

### 2.3 数据与报告生成（供静态页使用）

| 技术项 | 选型 | 说明 |
|--------|------|------|
| 数据拉取与指标 | **现有 ndx_rsi**（fetch_data、策略、run_signal） | 与 C-2 约束一致，不重复造轮子 |
| 5 年走势数据 | **现有数据管道** 输出为 **JSON**（时间序列数组） | 可由 Python 脚本在定时任务中调用现有逻辑并写 JSON |
| 当日信号 | **run_signal 输出** 转为 **JSON 或结构化文本** | 与现有 report 格式一致，便于前端展示“收盘价、EMA、波动率、推导逻辑、操作建议” |

### 2.4 设计系统（涉及 UI）

本项目涉及 **Web 端静态页面**，已按步骤 3 要求调用 **ui-ux-pro-max** 生成设计系统并持久化：

- **产出路径**：`design-system/指数数据与信号展示/MASTER.md`（项目根为 `index_data_analysis` 时的相对路径）
- **风格**：Glassmorphism（毛玻璃、层次感），适用于金融仪表盘
- **色彩**：Primary `#2563EB`、Secondary `#3B82F6`、CTA `#F97316`、Background `#F8FAFC`、Text `#1E293B`
- **字体**：Inter（标题与正文）
- **规范**：见 MASTER.md（按钮、卡片、间距、阴影、无障碍与响应式清单等）

技术方案设计（步骤 4）与代码开发（步骤 6）须引用该设计系统，保证界面一致性与可访问性。

---

## 3. 技术选型评估简表

| 维度 | 定时与推送 | 静态站点 |
|------|------------|----------|
| 技术成熟度 | 高（GitHub Actions、Python 广泛使用） | 高（HTML/JS、ECharts/Lightweight Charts 成熟） |
| 社区与生态 | 文档与示例丰富 | 图表库文档齐全、设计系统已生成 |
| 学习曲线 | 低（沿用现有 Python） | 低（无框架、设计系统已给定） |
| 性能与资源 | Actions 免费额度内可满足日频 | 静态资源 + 预生成数据，首屏与长期维护成本低 |
| 长期维护 | 配置化（Secrets）、与参考项目一致 | 静态文件易维护；数据由既有管道生成 |

---

## 4. 约束与依赖

- **C-1**：定时与推送实现参考 **daily_stock_analysis**（路径 `daily_stock_analysis`），其 Actions 与 Secrets 用法可直接复用。
- **C-2**：数据与策略以 **index_data_analysis** 现有实现为准，不新增数据源或策略逻辑。
- **C-3**：静态站点采用“静态文件 + 预生成数据”，不依赖实时后端 API。

---

## 5. 输出物与检查点

| 输出物 | 状态 |
|--------|------|
| 技术栈选型文档（本文档） | ✅ |
| 技术选型评估（上文第 3 节） | ✅ |
| 设计系统产出物 | ✅ `design-system/指数数据与信号展示/MASTER.md` |
| 文件名 | `03-technology-stack-selection.md`（本文档） |

- ✅ 已从需求出发选择技术栈，并做多维度评估。  
- ✅ 涉及 UI 部分已调用 ui-ux-pro-max 生成设计系统并持久化，供步骤 4、6 引用。  
- ✅ 未引入与现有项目冲突的技术；定时与推送与参考项目对齐。

**下一步**：完成本步骤后需用户确认；确认后进入步骤 4「技术方案设计」。
