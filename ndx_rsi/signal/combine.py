"""
组合逻辑：趋势 > 量能 > RSI。输出 TDD 约定的 signal dict。
上升趋势忽略单纯超买（除非缩量滞涨）；下降趋势忽略单纯超卖（除非缩量企稳）。
"""
import pandas as pd
from typing import Any, Dict

from ndx_rsi.signal.trend_volume import TREND_UP, TREND_DOWN, get_trend, get_volume_type
from ndx_rsi.signal.rsi_signals import (
    check_overbought_oversold,
    check_golden_death_cross,
)


def generate_signal_dict(
    df: pd.DataFrame,
    market_env: str,
    rsi_short_col: str = "rsi_9",
    rsi_long_col: str = "rsi_24",
    ma50_col: str = "ma50",
    volume_ratio_col: str = "volume_ratio",
) -> Dict[str, Any]:
    """
    对最后一根 K 线生成信号。df 需含 close, volume, rsi_9, rsi_24, ma50, volume_ratio。
    返回 {"signal": "buy"|"sell"|"hold", "position": float, "reason": str, ...}。
    """
    if df.empty or len(df) < 2:
        return {"signal": "hold", "position": 0.0, "reason": "insufficient_data"}

    row = df.iloc[-1]
    prev = df.iloc[-2]
    close = row.get("close", 0)
    rsi_s = row.get(rsi_short_col, 50)
    rsi_l = row.get(rsi_long_col, 50)
    vol_ratio = row.get(volume_ratio_col, 1.0)
    prices = df["close"]
    ma50 = df[ma50_col]

    trend = get_trend(prices, ma50)
    vol_type = get_volume_type(vol_ratio)

    ob, os = check_overbought_oversold(rsi_s, rsi_l, market_env)
    cross = check_golden_death_cross(
        rsi_s, rsi_l,
        prev.get(rsi_short_col, 50), prev.get(rsi_long_col, 50),
        market_env,
    )

    # 组合：优先金叉/死叉，再超买超卖（并做趋势过滤）
    if cross == "golden_cross" and vol_ratio >= 1.2:
        return {"signal": "buy", "position": 0.4, "reason": "golden_cross", "ts": str(df.index[-1])}
    if cross == "death_cross" and vol_ratio >= 1.2:
        return {"signal": "sell", "position": -0.4, "reason": "death_cross", "ts": str(df.index[-1])}

    if trend == TREND_UP:
        if os and vol_type == "down":  # 超卖 + 缩量企稳 → 买
            return {"signal": "buy", "position": 0.3, "reason": "oversell", "ts": str(df.index[-1])}
        if 45 <= rsi_s <= 55 and vol_type == "down":  # 回踩 50 加仓
            return {"signal": "buy", "position": 0.2, "reason": "trend_pullback", "ts": str(df.index[-1])}
        if ob and vol_type == "down":  # 超买 + 缩量滞涨 → 轻减
            return {"signal": "sell_light", "position": -0.2, "reason": "overbought", "ts": str(df.index[-1])}
    elif trend == TREND_DOWN:
        if ob and vol_ratio >= 1.2:  # 超买 + 放量 → 减
            return {"signal": "sell", "position": -0.3, "reason": "overbought", "ts": str(df.index[-1])}
        if 50 <= rsi_s <= 60 and vol_ratio >= 1.2:
            return {"signal": "sell", "position": -0.2, "reason": "trend_bounce_sell", "ts": str(df.index[-1])}
        if os and vol_type == "down":  # 超卖 + 缩量 → 轻仓试多
            return {"signal": "buy_light", "position": 0.3, "reason": "oversell", "ts": str(df.index[-1])}
    else:
        # 震荡：超买减、超卖加
        if ob:
            return {"signal": "sell", "position": -0.3, "reason": "overbought", "ts": str(df.index[-1])}
        if os:
            return {"signal": "buy", "position": 0.3, "reason": "oversell", "ts": str(df.index[-1])}

    return {"signal": "hold", "position": 0.0, "reason": "no_signal", "ts": str(df.index[-1])}
