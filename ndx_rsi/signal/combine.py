"""
组合逻辑：趋势 > 量能 > RSI；v2 可选顶/底背离。输出 TDD 约定的 signal dict。
上升趋势忽略单纯超买（除非缩量滞涨）；下降趋势忽略单纯超卖（除非缩量企稳）。
"""
import pandas as pd
from typing import Any, Dict, Optional

from ndx_rsi.signal.trend_volume import TREND_UP, TREND_DOWN, get_trend, get_volume_type
from ndx_rsi.signal.rsi_signals import (
    check_overbought_oversold,
    check_golden_death_cross,
    check_divergence,
)


def generate_signal_dict(
    df: pd.DataFrame,
    market_env: str,
    rsi_short_col: str = "rsi_9",
    rsi_long_col: str = "rsi_24",
    ma50_col: str = "ma50",
    volume_ratio_col: str = "volume_ratio",
    ma5_col: str = "ma5",
    ma20_col: str = "ma20",
    use_divergence: bool = False,
    divergence_lookback: int = 20,
    current_position_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    对最后一根 K 线生成信号。df 需含 close, volume, rsi_9, rsi_24, ma50, volume_ratio；可选 ma5（TASK-07）。
    TASK-11：current_position_info 为 {"direction": "long"|"short", "entry_reason": str} 时参与平仓判断。
    返回 {"signal": "buy"|"sell"|"hold"|"close", "position": float, "reason": str, ...}。
    """
    if df.empty or len(df) < 2:
        return {"signal": "hold", "position": 0.0, "reason": "insufficient_data"}

    row = df.iloc[-1]
    prev = df.iloc[-2]
    close = row.get("close", 0)
    rsi_s = row.get(rsi_short_col, 50)
    rsi_l = row.get(rsi_long_col, 50)
    vol_ratio = row.get(volume_ratio_col, 1.0)
    ma5 = row.get(ma5_col, None) if ma5_col in df.columns else None
    prices = df["close"]
    ma50 = df[ma50_col]

    # TASK-11：平仓信号（持仓 short + overbought 入场 + RSI<65 → close；long + oversell 入场 + RSI>35 → close）
    if current_position_info:
        direction = current_position_info.get("direction", "")
        entry_reason = current_position_info.get("entry_reason", "")
        if direction == "short" and entry_reason == "overbought" and rsi_s < 65:
            return {"signal": "close", "position": 0.0, "reason": "close_overbought_exit", "ts": str(df.index[-1])}
        if direction == "long" and entry_reason == "oversell" and rsi_s > 35:
            return {"signal": "close", "position": 0.0, "reason": "close_oversell_exit", "ts": str(df.index[-1])}
        if direction == "short" and entry_reason == "strong_overbought" and rsi_s < 65:
            return {"signal": "close", "position": 0.0, "reason": "close_overbought_exit", "ts": str(df.index[-1])}
        if direction == "long" and entry_reason == "strong_oversell" and rsi_s > 35:
            return {"signal": "close", "position": 0.0, "reason": "close_oversell_exit", "ts": str(df.index[-1])}

    trend = get_trend(prices, ma50)
    vol_type = get_volume_type(vol_ratio)

    ob, os = check_overbought_oversold(rsi_s, rsi_l, market_env)
    cross = check_golden_death_cross(
        rsi_s, rsi_l,
        prev.get(rsi_short_col, 50), prev.get(rsi_long_col, 50),
        market_env,
        close=close if close else None,
        ma5=float(ma5) if ma5 is not None and pd.notna(ma5) else None,
    )
    # v2 可选：顶/底背离
    divergence = None
    if use_divergence and len(df) >= divergence_lookback:
        divergence = check_divergence(
            df["close"], df[rsi_short_col],
            lookback=divergence_lookback,
            volume_ratio=vol_ratio,
            require_volume=False,
        )
    # 组合：金叉/死叉按趋势分路径（TASK-03 FIX-03）；再超买超卖；背离按趋势分支在下方处理（TASK-10）
    mid = (rsi_s + rsi_l) / 2
    if cross == "golden_cross":
        if trend == TREND_UP or trend == TREND_DOWN:
            if vol_ratio >= 1.2:
                return {"signal": "buy", "position": 0.4, "reason": "golden_cross", "ts": str(df.index[-1])}
        else:
            # 震荡：金叉需缩量 + midpoint 30-50；金叉 mid>50 且放量 → hold
            if mid > 50 and vol_ratio >= 1.2:
                pass
            elif vol_type == "down" and 30 <= mid <= 50:
                return {"signal": "buy", "position": 0.3, "reason": "golden_cross", "ts": str(df.index[-1])}
    if cross == "death_cross":
        if trend == TREND_UP or trend == TREND_DOWN:
            if vol_ratio >= 1.2:
                return {"signal": "sell", "position": -0.4, "reason": "death_cross", "ts": str(df.index[-1])}
        else:
            # 震荡：死叉需放量 + midpoint 50-70；死叉 mid<30 且缩量 → hold
            if mid < 30 and vol_type == "down":
                pass
            elif vol_ratio >= 1.2 and 50 <= mid <= 70:
                return {"signal": "sell", "position": -0.3, "reason": "death_cross", "ts": str(df.index[-1])}

    if trend == TREND_UP:
        # TASK-10：上升趋势只处理底背离 + vol≥1.2 → buy 0.5；忽略顶背离
        if use_divergence and divergence == "bullish_divergence" and vol_ratio >= 1.2:
            return {"signal": "buy", "position": 0.5, "reason": "bullish_divergence", "ts": str(df.index[-1])}
        # TASK-04 FIX-04：上升趋势回踩/超卖时放量 → 不买（资金出逃）
        if os and vol_ratio >= 1.2:
            return {"signal": "hold", "position": 0.0, "reason": "pullback_volume_reject", "ts": str(df.index[-1])}
        if os and vol_type == "down":  # 超卖 + 缩量企稳 → 买（TASK-08 强超卖 0.4）
            pos_buy = 0.4 if os == "strong_oversell" else 0.3
            return {"signal": "buy", "position": pos_buy, "reason": os, "ts": str(df.index[-1])}
        if 45 <= rsi_s <= 55 and vol_ratio >= 1.2:
            return {"signal": "hold", "position": 0.0, "reason": "pullback_volume_reject", "ts": str(df.index[-1])}
        if 45 <= rsi_s <= 55 and vol_type == "down":  # 回踩 50 加仓
            return {"signal": "buy", "position": 0.2, "reason": "trend_pullback", "ts": str(df.index[-1])}
        # TASK-05 FIX-05：上升趋势超买 + 放量 → 继续持仓，忽略超买（BRD）
        if ob and vol_ratio >= 1.2:
            return {"signal": "hold", "position": 0.0, "reason": "overbought_with_volume_ignore", "ts": str(df.index[-1])}
        if ob and vol_type == "down":  # 超买 + 缩量滞涨 → 轻减（TASK-08 强超买 -0.3）
            pos_sell = -0.3 if ob == "strong_overbought" else -0.2
            return {"signal": "sell_light", "position": pos_sell, "reason": ob, "ts": str(df.index[-1])}
    elif trend == TREND_DOWN:
        # TASK-10：下降趋势只处理顶背离 + 缩量 → sell -1.0 清仓；忽略底背离
        if use_divergence and divergence == "bearish_divergence" and vol_type == "down":
            return {"signal": "sell", "position": -1.0, "reason": "bearish_divergence", "ts": str(df.index[-1])}
        if ob and vol_ratio >= 1.2:  # 超买 + 放量 → 减（TASK-08 强超买 -0.4）
            pos_sell = -0.4 if ob == "strong_overbought" else -0.3
            return {"signal": "sell", "position": pos_sell, "reason": ob, "ts": str(df.index[-1])}
        # TASK-06 FIX-06：50-60 缩量反弹轻减、放量滞涨加重减
        if 50 <= rsi_s <= 60 and vol_type == "down":
            return {"signal": "sell_light", "position": -0.2, "reason": "trend_bounce_sell_light", "ts": str(df.index[-1])}
        if 50 <= rsi_s <= 60 and vol_ratio >= 1.2:
            return {"signal": "sell", "position": -0.4, "reason": "trend_bounce_sell", "ts": str(df.index[-1])}
        if os and vol_type == "down":  # 超卖 + 缩量 → 轻仓试多（TASK-08 强超卖 0.4）
            pos_buy = 0.4 if os == "strong_oversell" else 0.3
            return {"signal": "buy_light", "position": pos_buy, "reason": os, "ts": str(df.index[-1])}
    else:
        # TASK-10：震荡市底背离+缩量 → buy 0.3；顶背离+放量 → sell -0.3
        if use_divergence and divergence == "bullish_divergence" and vol_type == "down":
            return {"signal": "buy", "position": 0.3, "reason": "bullish_divergence", "ts": str(df.index[-1])}
        if use_divergence and divergence == "bearish_divergence" and vol_ratio >= 1.2:
            return {"signal": "sell", "position": -0.3, "reason": "bearish_divergence", "ts": str(df.index[-1])}
        # 震荡：超买需放量确认才减、超卖需缩量才加（TASK-08 强超买 -0.4 / 强超卖 0.4）
        if ob and vol_ratio >= 1.2:
            pos_sell = -0.4 if ob == "strong_overbought" else -0.3
            return {"signal": "sell", "position": pos_sell, "reason": ob, "ts": str(df.index[-1])}
        if os and vol_type == "down":
            pos_buy = 0.4 if os == "strong_oversell" else 0.3
            return {"signal": "buy", "position": pos_buy, "reason": os, "ts": str(df.index[-1])}

    return {"signal": "hold", "position": 0.0, "reason": "no_signal", "ts": str(df.index[-1])}
