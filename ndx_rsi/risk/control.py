"""
风控：极端行情禁止开仓（VIX>30 且 RSI 极值）、仓位上限、止损止盈比例。
"""
from typing import Any, Dict, Optional

from ndx_rsi.indicators.market_env import get_rsi_thresholds

# 极端行情：VIX 与 RSI 极值（无 VIX 时仅用 RSI 极值也可禁止）
VIX_EXTREME = 30
RSI_EXTREME_LOW = 10
RSI_EXTREME_HIGH = 90


def check_extreme_market(
    vix: Optional[float] = None,
    rsi: Optional[float] = None,
) -> bool:
    """若 VIX>30 且 (RSI<10 或 RSI>90)，返回 True，禁止新开仓。无 VIX 时仅看 RSI 极值。"""
    if vix is not None and vix > VIX_EXTREME:
        if rsi is not None and (rsi < RSI_EXTREME_LOW or rsi > RSI_EXTREME_HIGH):
            return True
    if rsi is not None and (rsi < RSI_EXTREME_LOW or rsi > RSI_EXTREME_HIGH):
        if vix is not None and vix > VIX_EXTREME:
            return True
        # 无 VIX 时仅 RSI 极值也视为极端
        if vix is None:
            return True
    return False


def apply_position_cap(
    position: float,
    market_env: str,
    rsi_short: Optional[float] = None,
    dynamic_cap_config: Optional[Dict[str, Any]] = None,
) -> float:
    """按市场环境限制仓位上限；TASK-12：牛市强超买/熊市强超卖时 cap 降至配置值（默认 0.5）。"""
    caps = {"bull": 0.8, "bear": 0.3, "oscillate": 0.5, "transition": 0.5}
    cap = caps.get(market_env, 0.5)
    if dynamic_cap_config is not None and rsi_short is not None:
        th = get_rsi_thresholds(market_env)
        strong_ob = th.get("strong_overbuy", 85)
        strong_os = th.get("strong_oversell", 15)
        if market_env == "bull" and rsi_short > strong_ob:
            cap = dynamic_cap_config.get("bull_overbought", 0.5)
        elif market_env == "bear" and rsi_short < strong_os:
            cap = dynamic_cap_config.get("bear_oversell", 0.5)
    if position > 0:
        return min(position, cap)
    return max(position, -cap)


def get_stop_loss_take_profit(
    close: float,
    signal: str,
    is_leverage_etf: bool = False,
    stop_ratio: Optional[float] = None,
    take_ratio: Optional[float] = None,
    reason: str = "",
    signal_risk_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """
    根据 design：ETF 止损 3%，杠杆 ETF 5%；止盈约 5–8%。
    TASK-09：若传入 reason 与 signal_risk_config，按 reason 取差异化比例。
    """
    if signal_risk_config and reason:
        entry = signal_risk_config.get(reason) or signal_risk_config.get("default")
        if entry:
            stop_ratio = entry.get("stop_loss_ratio", stop_ratio)
            take_ratio = entry.get("take_profit_ratio", take_ratio)
    if stop_ratio is None:
        stop_ratio = 0.05 if is_leverage_etf else 0.03
    if take_ratio is None:
        take_ratio = 0.07
    if signal in ("buy", "buy_light"):
        return {
            "stop_loss": close * (1 - stop_ratio),
            "take_profit": close * (1 + take_ratio),
        }
    if signal in ("sell", "sell_light"):
        return {
            "stop_loss": close * (1 + stop_ratio),
            "take_profit": close * (1 - take_ratio),
        }
    return {"stop_loss": close, "take_profit": close}
