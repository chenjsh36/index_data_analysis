# 开发步骤拆分（步骤 5）— v6

**文档类型**：开发任务拆分  
**依据**：`04-technical-design.md`  
**参考规范**：WBS、INVEST、Story Points

---

## 1. 任务清单（Task List）

| ID | 任务名称 | 描述 | 验收标准 | 依赖 | 估算 | 优先级 |
|----|----------|------|----------|------|------|--------|
| T1 | 通知脚本 run_signal_and_notify | 实现脚本：调用 run_signal 获取报告文本，按环境变量发邮件（SMTP）与钉钉（CUSTOM_WEBHOOK_URLS POST） | 本地或 CI 可运行；配置 EMAIL_* 或 CUSTOM_WEBHOOK_URLS 后能收到报告 | 无 | 2 | P0 |
| T2 | GitHub Actions daily_signal | 新增 .github/workflows/daily_signal.yml：schedule + workflow_dispatch，安装依赖后执行通知脚本 | 手动触发可成功跑信号并推送（需配置 Secrets） | T1 | 1 | P0 |
| T3 | 静态数据生成脚本 | 实现脚本或 CLI：拉 5 年 QQQ 写 timeseries.json，跑一次 signal 写 signal.json（格式见 TDD 3.2） | 产出 web/timeseries.json、web/signal.json，格式与 TDD 一致 | 无 | 2 | P0 |
| T4 | 静态站点 web/ | 新增 web/index.html + CSS + JS：ECharts 走势图（读 timeseries.json）、当日信号卡片（读 signal.json），遵循 design-system/MASTER.md | 本地 python -m http.server 后浏览器可查看图表与信号；风格与设计系统一致 | T3 | 3 | P0 |
| T5 | 文档与 README | 更新 README（v6 定时推送与静态站说明）、新增 docs/v6/06-code-development.md 记录实现与使用 | README 含 Actions 与静态站用法；06 文档可追溯实现项 | T2,T4 | 1 | P1 |

---

## 2. 任务依赖图（Dependency Graph）

```
    T1 ──> T2
    T3 ──> T4
    T2 ──> T5
    T4 ──> T5
```

- T1 与 T3 可并行开发；T2 依赖 T1；T4 依赖 T3（数据格式）；T5 依赖 T2、T4 完成。

---

## 3. 开发计划与里程碑

| 里程碑 | 包含任务 | 目标 |
|--------|----------|------|
| M1：定时推送可用 | T1, T2 | 在 GitHub 上配置后能每日/手动跑信号并收到邮件或钉钉 |
| M2：静态页可用 | T3, T4 | 本地生成 JSON 并启动静态服务后，浏览器可看 5 年走势与当日信号 |
| M3：文档收尾 | T5 | README 与 06 文档就绪，可交付 |

---

## 4. 输出物

- 任务清单（上表）
- 任务依赖图（本节 2）
- 开发计划/里程碑（本节 3）
- 文件名：`05-development-task-breakdown.md`（本文档）

**下一步**：按 T1 → T2、T3 → T4 → T5 顺序执行步骤 6（代码开发）。
