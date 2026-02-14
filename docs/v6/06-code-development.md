# 代码开发记录（步骤 6）— v6

**文档类型**：开发实现说明  
**依据**：`04-technical-design.md`、`05-development-task-breakdown.md`

---

## 1. 实现清单

| 任务 | 实现位置 | 说明 |
|------|----------|------|
| T1 通知脚本 | `scripts/run_signal_and_notify.py` | 调用 run_signal 逻辑得到报告文本；按环境变量发邮件（SMTP）、钉钉（CUSTOM_WEBHOOK_URLS POST） |
| T2 GitHub Actions | `.github/workflows/daily_signal.yml` | schedule 每日 UTC 22:00 + workflow_dispatch；安装依赖后执行 `PYTHONPATH=. python scripts/run_signal_and_notify.py` |
| T3 静态数据生成 | `scripts/generate_static_data.py` | 拉 5 年 QQQ 写 `web/timeseries.json`；跑一次 signal 写 `web/signal.json`（格式见 TDD 3.2） |
| T4 静态站点 | `web/index.html` | 单页：ECharts 走势图（读 timeseries.json）+ 当日信号卡片（读 signal.json）；风格遵循 design-system/指数数据与信号展示/MASTER.md（Inter、色彩、Glassmorphism） |
| T5 文档 | README.md、本文档 | README 增加 v6 小节；06 记录实现项与用法 |

---

## 2. 新增/修改文件

- **新增**：`scripts/run_signal_and_notify.py`、`scripts/generate_static_data.py`、`.github/workflows/daily_signal.yml`、`web/index.html`、`web/timeseries.json`、`web/signal.json`（占位，由 generate_static_data 覆盖）、`docs/v6/05-development-task-breakdown.md`、`docs/v6/06-code-development.md`
- **修改**：`requirements.txt`（增加 requests）、`ndx_rsi/report/signal_report.py`（增加 `signal_report_to_dict`）、`ndx_rsi/report/__init__.py`（导出 `signal_report_to_dict`）、`README.md`（v6 说明与文档索引）

---

## 3. 使用说明

- **推送**：在 GitHub 仓库 Settings → Secrets 配置 `EMAIL_SENDER`、`EMAIL_PASSWORD`、`EMAIL_RECEIVERS` 和/或 `CUSTOM_WEBHOOK_URLS`，启用 Actions 后每日自动跑信号并推送；也可在 Actions 页手动运行「每日信号」。
- **静态页**：本地执行 `PYTHONPATH=. python scripts/generate_static_data.py --out-dir web` 生成 JSON，再在 `web/` 下执行 `python3 -m http.server 8080`，浏览器打开 `http://localhost:8080`。

---

## 4. 验收对应

- FR-1～FR-3（定时跑信号、推送、可配置）：由 workflow + 通知脚本 + Secrets 满足。
- FR-4～FR-7（静态服务、5 年走势、当日信号、数据更新方式）：由 generate_static_data + web/index.html + 本地 http.server 满足。
- 设计系统：页面使用 Inter、约定色彩与卡片/阴影，符合 MASTER.md；先简单实现，未引入构建工具。

---

**步骤 6 完成。** 如需下一轮迭代（如 Actions 内自动生成并提交 JSON、或扩展渠道），可在需求层补充后继续开发。
