# 开发步骤拆分（Development Task Breakdown）— v3 BRD 对齐修正版

**文档版本**：3.0  
**产出日期**：2026-02-09  
**依据**：研发流程步骤 5 - 开发步骤拆分  
**上游输入**：`v3/04-technical-design.md`

---

## 一、里程碑计划

| 里程碑 | 包含任务 | 目标 |
|--------|----------|------|
| **M1 — Critical 修正** | TASK-01 ~ TASK-05 | 核心信号逻辑对齐 BRD，消除逻辑冲突 |
| **M2 — High 增强** | TASK-06 ~ TASK-10 | 信号确认条件补全、强度分级、信号级风控 |
| **M3 — Medium 完善** | TASK-11 ~ TASK-13 | 平仓信号、动态仓位、MA20 |
| **M4 — 验证** | TASK-14 | 回测对比、全量回归 |

---

## 二、任务依赖图

```
TASK-01 (配置+阈值修正)
   │
   ├──→ TASK-02 (震荡市量能确认)
   ├──→ TASK-03 (震荡市金叉死叉)
   ├──→ TASK-04 (上升趋势反向过滤)
   └──→ TASK-05 (上升趋势放量持仓)
            │
            ├──→ TASK-06 (下降趋势缩量减仓)
            ├──→ TASK-07 (MA5 + 金叉死叉增强)
            ├──→ TASK-08 (超买超卖强度分级)
            │        │
            │        ├──→ TASK-09 (信号级止损止盈)
            │        └──→ TASK-10 (背离分趋势)
            │                │
            │                ├──→ TASK-11 (平仓信号)
            │                ├──→ TASK-12 (动态仓位)
            │                └──→ TASK-13 (MA20)
            │
            └────────────────→ TASK-14 (回测对比+回归)
```

---

## 三、任务清单

### TASK-01: 配置修正与阈值更新

| 字段 | 内容 |
|------|------|
| **ID** | TASK-01 |
| **名称** | 配置修正与阈值更新 |
| **优先级** | P0 Critical |
| **对应需求** | FIX-02 |
| **估算** | S (0.5 天) |
| **依赖** | 无 |
| **描述** | 1. 修改 `strategy.yaml` 中 `oscillate` 阈值：`overbuy: 65`, `oversell: 35`, `strong_overbuy: 70`, `strong_oversell: 30`。2. 修改 `market_env.py` 中 `_THRESHOLDS` 的 `oscillate` 条目保持同步。3. 新增 `signal_risk` 和 `dynamic_cap` 配置段（结构预埋，后续任务填充逻辑）。 |
| **涉及文件** | `config/strategy.yaml`, `ndx_rsi/indicators/market_env.py` |
| **验收标准** | 1. 震荡市 `get_rsi_thresholds("oscillate")` 返回 `overbuy=65, oversell=35`。2. 配置新增段存在且格式正确。3. 现有单测不受影响（transition 等其他环境阈值不变）。 |

---

### TASK-02: 震荡市超买超卖增加成交量确认

| 字段 | 内容 |
|------|------|
| **ID** | TASK-02 |
| **名称** | 震荡市超买超卖增加成交量确认 |
| **优先级** | P0 Critical |
| **对应需求** | FIX-01 |
| **估算** | S (0.5 天) |
| **依赖** | TASK-01 |
| **描述** | 修改 `combine.py` 震荡分支（原第 85-90 行）：1. 超买信号需 `ob AND vol_ratio >= 1.2` 才输出 sell。2. 超卖信号需 `os AND vol_type == "down"` 才输出 buy。3. 量能不匹配时输出 hold。 |
| **涉及文件** | `ndx_rsi/signal/combine.py` |
| **验收标准** | 1. 震荡市 RSI=66 + vol_ratio=0.7 → hold（非 sell）。2. 震荡市 RSI=66 + vol_ratio=1.3 → sell -0.3。3. 震荡市 RSI=34 + vol_ratio=1.3 → hold（非 buy）。4. 震荡市 RSI=34 + vol_ratio=0.7 → buy 0.3。 |

---

### TASK-03: 震荡市金叉/死叉量能方向修正

| 字段 | 内容 |
|------|------|
| **ID** | TASK-03 |
| **名称** | 震荡市金叉/死叉量能方向修正 |
| **优先级** | P0 Critical |
| **对应需求** | FIX-03 |
| **估算** | M (1 天) |
| **依赖** | TASK-01 |
| **描述** | 修改 `combine.py` 金叉/死叉处理：1. 将统一的金叉/死叉判断拆分为趋势内和震荡两条路径。2. 趋势内（UP/DOWN）：维持现有 `vol_ratio >= 1.2` 逻辑。3. 震荡市：金叉需 `vol_type == "down"` + midpoint 30-50；死叉需 `vol_ratio >= 1.2` + midpoint 50-70。4. 新增假信号过滤：震荡市金叉 mid>50 + 放量 → hold；死叉 mid<30 + 缩量 → hold。 |
| **涉及文件** | `ndx_rsi/signal/combine.py` |
| **验收标准** | 1. 震荡市金叉 + vol_ratio=1.3 → hold（非 buy）。2. 震荡市金叉 + vol_ratio=0.7 + mid=40 → buy 0.3。3. 震荡市死叉 + vol_ratio=1.3 + mid=60 → sell -0.3。4. 震荡市死叉 + vol_ratio=0.7 → hold。5. 上升趋势金叉 + vol_ratio=1.3 → buy 0.4（行为不变）。 |

---

### TASK-04: 上升趋势放量下跌反向过滤

| 字段 | 内容 |
|------|------|
| **ID** | TASK-04 |
| **名称** | 上升趋势放量下跌反向过滤 |
| **优先级** | P0 Critical |
| **对应需求** | FIX-04 |
| **估算** | S (0.5 天) |
| **依赖** | TASK-01 |
| **描述** | 修改 `combine.py` 上升趋势分支：1. 在 RSI 回踩（os 或 40≤rsi≤50）判断中增加放量检查。2. 若 `vol_ratio >= 1.2` → 返回 hold（reason="pullback_volume_reject"）。3. 仅 `vol_type == "down"` 时允许买入。4. RSI 45-55 回踩加仓（原第 74 行）同样增加非放量条件。 |
| **涉及文件** | `ndx_rsi/signal/combine.py` |
| **验收标准** | 1. 上升趋势 RSI=43 + vol_ratio=1.3 → hold。2. 上升趋势 RSI=43 + vol_ratio=0.7 → buy 0.3。3. 上升趋势 RSI=48 + vol_ratio=1.3 → hold。4. 上升趋势 RSI=48 + vol_ratio=0.7 → buy 0.2。 |

---

### TASK-05: 上升趋势放量超买显式持仓

| 字段 | 内容 |
|------|------|
| **ID** | TASK-05 |
| **名称** | 上升趋势放量超买显式持仓 |
| **优先级** | P0 Critical |
| **对应需求** | FIX-05 |
| **估算** | XS (0.25 天) |
| **依赖** | TASK-01 |
| **描述** | 修改 `combine.py` 上升趋势超买分支：1. 在 `ob and vol_type == "down"` 之前增加判断：`ob and vol_ratio >= 1.2` → hold（reason="overbought_with_volume_ignore"）。2. 添加 BRD 来源注释。 |
| **涉及文件** | `ndx_rsi/signal/combine.py` |
| **验收标准** | 1. 上升趋势 RSI=78 + vol_ratio=1.3 → hold（非 sell_light）。2. 上升趋势 RSI=78 + vol_ratio=0.7 → sell_light -0.2。 |

---

### TASK-06: 下降趋势缩量反弹减仓

| 字段 | 内容 |
|------|------|
| **ID** | TASK-06 |
| **名称** | 下降趋势缩量反弹减仓 |
| **优先级** | P1 High |
| **对应需求** | FIX-06 |
| **估算** | S (0.5 天) |
| **依赖** | TASK-04 |
| **描述** | 修改 `combine.py` 下降趋势分支：1. 新增规则：`50 <= rsi_s <= 60` 且 `vol_type == "down"` → sell_light -0.2（reason="trend_bounce_sell_light"）。2. 调整放量滞涨仓位：`50 <= rsi_s <= 60` 且 `vol_ratio >= 1.2` → sell -0.4（原 -0.2 提升至 -0.4）。 |
| **涉及文件** | `ndx_rsi/signal/combine.py` |
| **验收标准** | 1. 下降趋势 RSI=55 + vol_ratio=0.7 → sell_light -0.2。2. 下降趋势 RSI=55 + vol_ratio=1.3 → sell -0.4。 |

---

### TASK-07: 新增 MA5 + 金叉/死叉确认增强

| 字段 | 内容 |
|------|------|
| **ID** | TASK-07 |
| **名称** | 新增 MA5 + 金叉/死叉确认增强 |
| **优先级** | P1 High |
| **对应需求** | FIX-07 |
| **估算** | M (1 天) |
| **依赖** | TASK-04 |
| **描述** | 1. `indicators/ma.py` 新增 `calculate_ma5()`。2. `indicators/__init__.py` 导出。3. `rsi_signals.py` 的 `check_golden_death_cross()` 新增 `close`, `ma5` 可选参数：无效区间过滤（金叉 mid>70 → None，死叉 mid<30 → None）；金叉需 close > ma5；死叉需 close < ma5。4. `ndx_short.py` 预计算 ma5 并传入。5. `runner.py` 预计算 `df["ma5"]`。6. `combine.py` 传递 close、ma5 到金叉/死叉检查。 |
| **涉及文件** | `indicators/ma.py`, `indicators/__init__.py`, `signal/rsi_signals.py`, `signal/combine.py`, `strategy/ndx_short.py`, `backtest/runner.py` |
| **验收标准** | 1. MA5 计算正确（与 pandas rolling(5) 一致）。2. 金叉在 mid=72 → None。3. 死叉在 mid=28 → None。4. 金叉 + close < ma5 → None。5. 金叉 + close > ma5 + mid=45 → "golden_cross"。 |

---

### TASK-08: 超买超卖强度分级

| 字段 | 内容 |
|------|------|
| **ID** | TASK-08 |
| **名称** | 超买超卖强度分级 |
| **优先级** | P1 High |
| **对应需求** | FIX-08 |
| **估算** | M (1 天) |
| **依赖** | TASK-05 |
| **描述** | 1. 修改 `rsi_signals.py` 的 `check_overbought_oversold()` 返回 `"strong_overbought"` / `"strong_oversell"` 新值。2. 修改 `combine.py` 各趋势分支根据强度调整仓位：普通超买 sell -0.2/-0.3，强超买 sell -0.3/-0.4；普通超卖 buy 0.3，强超卖 buy 0.4。3. 确保所有分支正确处理新返回值（`"strong_*"` 也视为超买/超卖）。 |
| **涉及文件** | `ndx_rsi/signal/rsi_signals.py`, `ndx_rsi/signal/combine.py` |
| **验收标准** | 1. 牛市 RSI=82 → `("strong_overbought", None)`。2. 牛市 RSI=78 → `("overbought", None)`。3. 上升趋势 + strong_overbought + 缩量 → sell_light -0.3（非 -0.2）。4. 震荡 + strong_oversell + 缩量 → buy 0.4（非 0.3）。 |

---

### TASK-09: 信号级止损止盈

| 字段 | 内容 |
|------|------|
| **ID** | TASK-09 |
| **名称** | 信号级止损止盈 |
| **优先级** | P1 High |
| **对应需求** | FIX-09 |
| **估算** | M (1 天) |
| **依赖** | TASK-08 |
| **描述** | 1. 修改 `control.py` 的 `get_stop_loss_take_profit()` 新增 `reason`, `signal_risk_config` 参数，按 reason 查找差异化比例。2. 在 `strategy.yaml` 的 `signal_risk` 段配置各信号类型比例。3. 修改 `ndx_short.py` 的 `calculate_risk()` 传入 reason 和 signal_risk_config。 |
| **涉及文件** | `ndx_rsi/risk/control.py`, `config/strategy.yaml`, `ndx_rsi/strategy/ndx_short.py` |
| **验收标准** | 1. reason="overbought" → stop_loss=2%, take_profit=5%。2. reason="golden_cross" → stop_loss=3%, take_profit=7%。3. reason="bullish_divergence" → stop_loss=4%, take_profit=8%。4. reason="" (空) → 使用默认 3%/7%。 |

---

### TASK-10: 背离信号区分趋势场景

| 字段 | 内容 |
|------|------|
| **ID** | TASK-10 |
| **名称** | 背离信号区分趋势场景 |
| **优先级** | P1 High |
| **对应需求** | FIX-10 |
| **估算** | M (1 天) |
| **依赖** | TASK-08 |
| **描述** | 修改 `combine.py` 背离处理逻辑：1. 将背离信号从顶部统一判断移入各趋势分支。2. 上升趋势：只处理底背离（bullish）+ vol≥1.2 → buy 0.5；忽略顶背离。3. 下降趋势：只处理顶背离（bearish）+ vol_type=="down" → sell -1.0（清仓）；忽略底背离。4. 震荡市：底背离+缩量 → buy 0.3；顶背离+放量 → sell -0.3。 |
| **涉及文件** | `ndx_rsi/signal/combine.py` |
| **验收标准** | 1. 上升趋势 + bullish_divergence + vol=1.3 → buy 0.5。2. 上升趋势 + bearish_divergence → hold。3. 下降趋势 + bearish_divergence + vol=0.7 → sell -1.0。4. 下降趋势 + bullish_divergence → hold。 |

---

### TASK-11: 平仓信号

| 字段 | 内容 |
|------|------|
| **ID** | TASK-11 |
| **名称** | 平仓信号 |
| **优先级** | P2 Medium |
| **对应需求** | FIX-11 |
| **估算** | M (1 天) |
| **依赖** | TASK-10 |
| **描述** | 1. `combine.py` 的 `generate_signal_dict()` 新增 `current_position_info` 可选参数（dict: direction + entry_reason）。2. 在信号主逻辑前判断：持仓 short + "overbought" 入场 + RSI < 65 → close；持仓 long + "oversell" 入场 + RSI > 35 → close。3. `runner.py` 传入当前持仓信息。 |
| **涉及文件** | `ndx_rsi/signal/combine.py`, `ndx_rsi/strategy/ndx_short.py`, `ndx_rsi/backtest/runner.py` |
| **验收标准** | 1. 持仓 short + entry_reason="overbought" + RSI=64 → signal="close"。2. 持仓 long + entry_reason="oversell" + RSI=36 → signal="close"。3. 无持仓信息时行为不变。 |

---

### TASK-12: 动态仓位上限

| 字段 | 内容 |
|------|------|
| **ID** | TASK-12 |
| **名称** | 动态仓位上限 |
| **优先级** | P2 Medium |
| **对应需求** | FIX-12 |
| **估算** | S (0.5 天) |
| **依赖** | TASK-08 |
| **描述** | 1. 修改 `control.py` 的 `apply_position_cap()` 新增 `rsi_short`, `dynamic_cap_config` 参数。2. 牛市 RSI > strong_overbuy → cap 降至 dynamic_cap 配置值（默认 0.5）。3. 熊市 RSI < strong_oversell → cap 升至配置值（默认 0.5）。4. `ndx_short.py` 传入 rsi_short 和 dynamic_cap 配置。 |
| **涉及文件** | `ndx_rsi/risk/control.py`, `ndx_rsi/strategy/ndx_short.py` |
| **验收标准** | 1. 牛市 RSI=86 → cap=0.5（非 0.8）。2. 熊市 RSI=14 → cap=0.5（非 0.3）。3. 牛市 RSI=75 → cap=0.8（不变）。4. 不传 dynamic_cap_config 时行为不变。 |

---

### TASK-13: 新增 MA20

| 字段 | 内容 |
|------|------|
| **ID** | TASK-13 |
| **名称** | 新增 MA20 |
| **优先级** | P2 Medium |
| **对应需求** | FIX-13 |
| **估算** | S (0.5 天) |
| **依赖** | TASK-10 |
| **描述** | 1. `indicators/ma.py` 新增 `calculate_ma20()`。2. `indicators/__init__.py` 导出。3. `runner.py` 预计算 `df["ma20"]`。4. `ndx_short.py` 预计算 ma20。5. `combine.py` 接收 `ma20_col` 参数（已在 TASK-02 时预埋签名），在下降趋势超卖买入时可选增强：close > ma20 时信号可靠度更高。 |
| **涉及文件** | `indicators/ma.py`, `indicators/__init__.py`, `backtest/runner.py`, `strategy/ndx_short.py`, `signal/combine.py` |
| **验收标准** | 1. MA20 计算值与 `df["close"].rolling(20).mean()` 一致。2. 下降趋势超卖 + close > ma20 时信号正常生成。 |

---

### TASK-14: 回测对比与回归验证

| 字段 | 内容 |
|------|------|
| **ID** | TASK-14 |
| **名称** | 回测对比与回归验证 |
| **优先级** | P0 (贯穿) |
| **对应需求** | 全部 FIX |
| **估算** | M (1 天) |
| **依赖** | TASK-01 ~ TASK-13 全部完成 |
| **描述** | 1. 使用 v2 代码运行基线回测（QQQ, 2018-2025），记录绩效指标。2. 使用 v3 代码运行同参数回测。3. 对比：信号数量、胜率、盈亏比、最大回撤、夏普比率。4. 编写对比报告。5. 确认无回归问题（transition/bull/bear 环境下信号不被意外破坏）。 |
| **涉及文件** | `backtest/runner.py`（运行）、新建对比报告 |
| **验收标准** | 1. v3 信号数量 ≤ v2（更严格过滤）。2. v3 胜率 ≥ v2。3. 对比报告包含完整指标对照表。4. 无意外的信号缺失（如牛市/熊市核心信号仍正常触发）。 |

---

## 四、任务汇总与排期

| 任务 | 优先级 | 估算 | 依赖 | 里程碑 |
|------|--------|------|------|--------|
| TASK-01 配置+阈值修正 | P0 | S | 无 | M1 |
| TASK-02 震荡市量能确认 | P0 | S | T01 | M1 |
| TASK-03 震荡市金叉死叉 | P0 | M | T01 | M1 |
| TASK-04 上升趋势反向过滤 | P0 | S | T01 | M1 |
| TASK-05 上升趋势放量持仓 | P0 | XS | T01 | M1 |
| TASK-06 下降趋势缩量减仓 | P1 | S | T04 | M2 |
| TASK-07 MA5 + 金叉增强 | P1 | M | T04 | M2 |
| TASK-08 强度分级 | P1 | M | T05 | M2 |
| TASK-09 信号级止损止盈 | P1 | M | T08 | M2 |
| TASK-10 背离分趋势 | P1 | M | T08 | M2 |
| TASK-11 平仓信号 | P2 | M | T10 | M3 |
| TASK-12 动态仓位 | P2 | S | T08 | M3 |
| TASK-13 MA20 | P2 | S | T10 | M3 |
| TASK-14 回测对比 | P0 | M | 全部 | M4 |

**总估算**：约 9.25 天（S=0.5d, M=1d, XS=0.25d）

---

## 五、并行开发建议

M1 内部可并行：TASK-02、TASK-03、TASK-04、TASK-05 均仅依赖 TASK-01，可在 TASK-01 完成后并行开发（都是修改 `combine.py` 的不同分支，注意合并冲突）。

M2 内部部分可并行：TASK-06、TASK-07 可并行（不同文件）；TASK-09、TASK-10 可并行（不同逻辑段）。

建议实际开发时按**顺序逐个完成**（单人开发），每完成一个任务运行单测确认，避免 `combine.py` 多处并行修改导致合并困难。

---

## 六、检查点

| 检查项 | 状态 |
|--------|------|
| 任务粒度（0.25 ~ 1 天） | 已确认 |
| 每个任务有验收标准 | 已确认 |
| 依赖关系已识别 | 已确认 |
| 里程碑划分合理 | 已确认 |

---

**下一步**：确认后进入「步骤 6：代码开发」，按 TASK-01 → TASK-14 顺序逐个实现。
