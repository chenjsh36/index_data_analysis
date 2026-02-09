"""
RSI 信号：超买超卖（按阈值）、金叉/死叉（9 日上穿/下穿 24 日）。
与 design.md 一致；背离首版简化（可后续扩展）。
"""
import pandas as pd
from typing import Any, Dict, Optional, Tuple

from ndx_rsi.indicators.market_env import get_rsi_thresholds


def check_overbought_oversold(
    rsi_short: float,
    rsi_long: float,
    market_env: str,
) -> Tuple[Optional[str], Optional[str]]:
    """
    返回 (overbought_reason, oversell_reason)。若未触发则为 None。
    如 overbought: "overbought", oversell: "oversell"。
    """
    th = get_rsi_thresholds(market_env)
    ob = th.get("overbuy", 70)
    os = th.get("oversell", 30)
    if rsi_short >= ob:
        return "overbought", None
    if rsi_short <= os:
        return None, "oversell"
    return None, None


def check_golden_death_cross(
    rsi_short_cur: float,
    rsi_long_cur: float,
    rsi_short_prev: float,
    rsi_long_prev: float,
    market_env: str,
) -> Optional[str]:
    """
    金叉：short 上穿 long；死叉：short 下穿 long。
    交叉位置需在合理区间（震荡 30–50 金叉 / 50–70 死叉等）。返回 "golden_cross" / "death_cross" / None。
    """
    golden = rsi_short_prev < rsi_long_prev and rsi_short_cur > rsi_long_cur
    death = rsi_short_prev > rsi_long_prev and rsi_short_cur < rsi_long_cur
    mid = (rsi_short_cur + rsi_long_cur) / 2
    if golden and 30 <= mid <= 60:
        return "golden_cross"
    if death and 40 <= mid <= 70:
        return "death_cross"
    return None
