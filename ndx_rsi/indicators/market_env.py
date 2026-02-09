"""
市场环境识别：50 日均线斜率 + 价格与均线关系 → bull/bear/oscillate/transition。
RSI 阈值表与 design.md 一致。
"""
import numpy as np
import pandas as pd
from typing import Dict, Any

# 斜率阈值：近 SLOPE_LOOKBACK 日的 MA50 斜率
SLOPE_LOOKBACK = 20
# 震荡：价格在 MA50 ±3% 内波动
OSCILLATE_RANGE = 0.03
# 趋势判定斜率阈值
SLOPE_UP = 0.001
SLOPE_DOWN = -0.001
SLOPE_FLAT_LOW = -0.005
SLOPE_FLAT_HIGH = 0.005

# 与 design.md 一致的 RSI 阈值
_THRESHOLDS = {
    "bull": {"overbuy": 80, "strong_overbuy": 85, "oversell": 40, "strong_oversell": 35},
    "bear": {"overbuy": 60, "strong_overbuy": 65, "oversell": 20, "strong_oversell": 15},
    "oscillate": {"overbuy": 70, "strong_overbuy": 75, "oversell": 30, "strong_oversell": 25},
    "transition": {"overbuy": 70, "strong_overbuy": 75, "oversell": 30, "strong_oversell": 25},
}


def judge_market_env(prices: pd.Series, ma50: pd.Series) -> str:
    """
    识别市场环境：bull / bear / oscillate / transition。
    上升：MA50 斜率>0 且最近收盘价在 MA50 上方；下降：斜率<0 且收盘在下方；
    震荡：斜率近平且价格在 MA50±3% 内。
    """
    if len(prices) < SLOPE_LOOKBACK or len(ma50) < SLOPE_LOOKBACK:
        return "transition"
    p = prices.iloc[-SLOPE_LOOKBACK:].values
    m = ma50.iloc[-SLOPE_LOOKBACK:].values
    slope = np.polyfit(np.arange(len(m)), m, 1)[0]
    # 归一化斜率（相对当前均线水平）
    slope_pct = slope / (m[-1] + 1e-10)
    last_price = prices.iloc[-1]
    last_ma = ma50.iloc[-1]
    if last_ma <= 0:
        return "transition"
    diff_pct = (last_price - last_ma) / last_ma
    # 连续 2 日收盘价与 MA50 关系（简化：用最近一根）
    if slope_pct > SLOPE_UP and diff_pct >= 0:
        return "bull"
    if slope_pct < SLOPE_DOWN and diff_pct <= 0:
        return "bear"
    if SLOPE_FLAT_LOW <= slope_pct <= SLOPE_FLAT_HIGH:
        if abs(diff_pct) <= OSCILLATE_RANGE:
            return "oscillate"
    return "transition"


def get_rsi_thresholds(market_env: str) -> Dict[str, Any]:
    """返回该市场环境下的 overbuy/oversell/strong_* 阈值。"""
    return _THRESHOLDS.get(market_env, _THRESHOLDS["transition"]).copy()
