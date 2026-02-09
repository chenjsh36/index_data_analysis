# v2 文档说明

v2 基于 **v1 简化实现与回测影响分析**（`../v1/07-simplifications-and-backtest-impact.md`）中的优化点，对需求与实现做增量梳理，不替代 v1 主流程。

## 文档索引

| 步骤 | 文档 | 说明 |
|------|------|------|
| 1 - 需求梳理 | [01-requirements_gathering.md](./01-requirements_gathering.md) | v2 增量需求清单、用户故事、用例；5W1H、MoSCoW、INVEST |
| 4 - 技术方案设计 | [04-technical-design.md](./04-technical-design.md) | v2 回测引擎（止损止盈、回撤熔断、标准绩效）、market_env 连续 2 日、可选背离、配置扩展 |
| 5 - 开发步骤拆分 | [05-development-task-breakdown.md](./05-development-task-breakdown.md) | v2 增量任务 T-v2-1～T-v2-8、依赖与里程碑 |
| 6 - 代码开发 | [06-code-development.md](./06-code-development.md) | v2 实现摘要、配置说明、运行与验收 |

后续可补充（按研发流程）：

- **02-requirements-documentation.md**：v2 需求规格（SRS/PRD 增量）
- **03-technology-stack-selection.md**：沿用 v1，或仅说明无变更
- **06-code-development.md**：v2 代码实现与验收

## v2 范围摘要

| 优先级 | 内容 | 对应需求 ID |
|--------|------|-------------|
| P0 | 回测中接入止损/止盈出场 | FR-v2-01 |
| P1 | 市场环境改为「连续 2 日」 | FR-v2-03 |
| P1 | 绩效指标按标准定义（profit_factor、夏普） | FR-v2-04 |
| P2 | 回测回撤熔断（可选） | FR-v2-05 |
| P2 | 顶/底背离实现（可选） | FR-v2-06 |

上游依据：`docs/v1/07-simplifications-and-backtest-impact.md` §3 建议的后续动作。
