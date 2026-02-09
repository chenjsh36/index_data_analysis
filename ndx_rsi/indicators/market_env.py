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
    "oscillate": {"overbuy": 65, "strong_overbuy": 70, "oversell": 35, "strong_oversell": 30},
    "transition": {"overbuy": 70, "strong_overbuy": 75, "oversell": 30, "strong_oversell": 25},
}


def judge_market_env(prices: pd.Series, ma50: pd.Series) -> str:
    """
    识别市场环境：bull / bear / oscillate / transition。
    v2: 牛/熊需连续 2 日收盘价与 MA50 关系（站上/跌破），与 TDD 一致。
    上升：MA50 斜率>0 且最近 2 日收盘均≥对应日 MA50；下降：斜率<0 且最近 2 日收盘均≤对应日 MA50；
    震荡：斜率近平且价格在 MA50±3% 内。
    """
    if len(prices) < SLOPE_LOOKBACK or len(ma50) < SLOPE_LOOKBACK:
        return "transition"
    if len(prices) < 2 or len(ma50) < 2:
        return "transition"
    p = prices.iloc[-SLOPE_LOOKBACK:].values
    m = ma50.iloc[-SLOPE_LOOKBACK:].values
    slope = np.polyfit(np.arange(len(m)), m, 1)[0]
    slope_pct = slope / (m[-1] + 1e-10)
    # 连续 2 日：最近 2 根 K 线收盘价与对应日 MA50 比较
    close_2 = prices.iloc[-2:].values
    ma50_2 = ma50.iloc[-2:].values
    if (ma50_2 <= 0).any():
        return "transition"
    both_above = (close_2 >= ma50_2 - 1e-10).all()
    both_below = (close_2 <= ma50_2 + 1e-10).all()
    if slope_pct > SLOPE_UP and both_above:
        return "bull"
    if slope_pct < SLOPE_DOWN and both_below:
        return "bear"
    last_price = prices.iloc[-1]
    last_ma = ma50.iloc[-1]
    diff_pct = (last_price - last_ma) / last_ma
    if SLOPE_FLAT_LOW <= slope_pct <= SLOPE_FLAT_HIGH:
        if abs(diff_pct) <= OSCILLATE_RANGE:
            return "oscillate"
    return "transition"


def get_rsi_thresholds(market_env: str) -> Dict[str, Any]:
    """返回该市场环境下的 overbuy/oversell/strong_* 阈值。"""
    return _THRESHOLDS.get(market_env, _THRESHOLDS["transition"]).copy()
