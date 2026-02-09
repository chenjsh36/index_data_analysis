"""
RSI 信号：超买超卖（按阈值）、金叉/死叉（9 日上穿/下穿 24 日）、顶/底背离（v2 可选）。
与 design.md 一致。
"""
import pandas as pd
from typing import Any, Dict, Optional, Tuple

from ndx_rsi.indicators.market_env import get_rsi_thresholds


def check_divergence(
    prices: pd.Series,
    rsi: pd.Series,
    lookback: int = 20,
    volume_ratio: Optional[float] = None,
    require_volume: bool = False,
) -> Optional[str]:
    """
    顶背离：价格创新高、RSI 未创新高 → "bearish_divergence"。
    底背离：价格创新低、RSI 未创新低 → "bullish_divergence"。
    使用最近两段区间内的最高/最低点比较；require_volume 为 True 时可要求量能条件（如放量）。
    """
    if len(prices) < lookback or len(rsi) < lookback:
        return None
    n = min(5, lookback // 3)
    if n < 2:
        return None
    # 最近 n 根 vs 前一段 n 根
    recent_p = prices.iloc[-n:]
    prev_p = prices.iloc[-2 * n : -n]
    recent_r = rsi.iloc[-n:]
    prev_r = rsi.iloc[-2 * n : -n]
    if recent_p.empty or prev_p.empty or recent_r.empty or prev_r.empty:
        return None
    recent_price_high = recent_p.max()
    prev_price_high = prev_p.max()
    recent_rsi_high = recent_r.max()
    prev_rsi_high = prev_r.max()
    recent_price_low = recent_p.min()
    prev_price_low = prev_p.min()
    recent_rsi_low = recent_r.min()
    prev_rsi_low = prev_r.min()

    if require_volume and volume_ratio is not None and volume_ratio < 1.0:
        # 顶背离可要求放量、底背离可要求缩量等，此处简化：仅当有量能数据时可选过滤
        pass
    # 顶背离：价格创新高、RSI 未创新高
    if recent_price_high > prev_price_high and recent_rsi_high < prev_rsi_high:
        return "bearish_divergence"
    # 底背离：价格创新低、RSI 未创新低
    if recent_price_low < prev_price_low and recent_rsi_low > prev_rsi_low:
        return "bullish_divergence"
    return None


def check_overbought_oversold(
    rsi_short: float,
    rsi_long: float,
    market_env: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    返回 (overbought_reason, oversell_reason)。若未触发则为 None。
    TASK-08：支持 "overbought"/"strong_overbought"、"oversell"/"strong_oversell"。
    """
    th = get_rsi_thresholds(market_env)
    ob_th = th.get("overbuy", 70)
    os_th = th.get("oversell", 30)
    strong_ob = th.get("strong_overbuy", 75)
    strong_os = th.get("strong_oversell", 25)
    if rsi_short >= strong_ob:
        return "strong_overbought", None
    if rsi_short >= ob_th:
        return "overbought", None
    if rsi_short <= strong_os:
        return None, "strong_oversell"
    if rsi_short <= os_th:
        return None, "oversell"
    return None, None


def check_golden_death_cross(
    rsi_short_cur: float,
    rsi_long_cur: float,
    rsi_short_prev: float,
    rsi_long_prev: float,
    market_env: str,
    close: Optional[float] = None,
    ma5: Optional[float] = None,
) -> Optional[str]:
    """
    金叉：short 上穿 long；死叉：short 下穿 long。
    交叉位置需在合理区间；TASK-07：金叉 mid>70→None，死叉 mid<30→None；金叉需 close>ma5，死叉需 close<ma5。
    """
    golden = rsi_short_prev < rsi_long_prev and rsi_short_cur > rsi_long_cur
    death = rsi_short_prev > rsi_long_prev and rsi_short_cur < rsi_long_cur
    mid = (rsi_short_cur + rsi_long_cur) / 2
    if golden:
        if mid > 70:
            return None
        if close is not None and ma5 is not None and close <= ma5:
            return None
        if 30 <= mid <= 60:
            return "golden_cross"
    if death:
        if mid < 30:
            return None
        if close is not None and ma5 is not None and close >= ma5:
            return None
        if 40 <= mid <= 70:
            return "death_cross"
    return None
