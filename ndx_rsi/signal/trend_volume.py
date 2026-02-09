"""
趋势判定（50 日均线斜率 + 收盘价与 MA50）+ 量能分类（放量/缩量/巨量/地量）。
与 design.md 一致。
"""
import numpy as np
import pandas as pd
from typing import Literal

TREND_UP = "up"
TREND_DOWN = "down"
TREND_SIDE = "side"
VOLUME_UP = "up"      # 放量 ≥1.2
VOLUME_DOWN = "down"  # 缩量 ≤0.8
VOLUME_HUGE = "huge"  # 巨量 ≥1.5
VOLUME_GROUND = "ground"  # 地量 ≤0.5


def get_trend(prices: pd.Series, ma50: pd.Series, lookback: int = 5) -> str:
    """
    趋势：上升=斜率>0 且最近连续 2 日收盘≥MA50；下降=斜率<0 且收盘≤MA50；否则震荡。
    """
    if len(prices) < lookback + 2 or len(ma50) < lookback + 2:
        return TREND_SIDE
    ma = ma50.iloc[-lookback:].values
    slope = np.polyfit(np.arange(len(ma)), ma, 1)[0]
    slope_pct = slope / (ma[-1] + 1e-10)
    # 最近 2 根
    close = prices.iloc[-2:].values
    ma2 = ma50.iloc[-2:].values
    if slope_pct > 0.0005 and (close >= ma2 - 1e-8).all():
        return TREND_UP
    if slope_pct < -0.0005 and (close <= ma2 + 1e-8).all():
        return TREND_DOWN
    return TREND_SIDE


def get_volume_type(volume_ratio: float) -> str:
    """量能类型：≥1.5 巨量，≥1.2 放量，≤0.5 地量，≤0.8 缩量。"""
    if volume_ratio >= 1.5:
        return VOLUME_HUGE
    if volume_ratio >= 1.2:
        return VOLUME_UP
    if volume_ratio <= 0.5:
        return VOLUME_GROUND
    if volume_ratio <= 0.8:
        return VOLUME_DOWN
    return "normal"
