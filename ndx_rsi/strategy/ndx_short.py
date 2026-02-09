"""
NDX 短线策略：从配置读取 RSI 周期与阈值，调用计算层+信号层+风控层。
"""
import pandas as pd
from typing import Any, Dict

from ndx_rsi.strategy.base import BaseTradingStrategy
from ndx_rsi.indicators import (
    calculate_rsi_handwrite,
    calculate_ma,
    calculate_volume_ratio,
    judge_market_env,
)
from ndx_rsi.signal.combine import generate_signal_dict
from ndx_rsi.risk.control import (
    check_extreme_market,
    apply_position_cap,
    get_stop_loss_take_profit,
)


class NDXShortTermRSIStrategy(BaseTradingStrategy):
    """纳斯达克100 短线（3–10 天）RSI 策略。"""

    def generate_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        if data.empty or len(data) < 50:
            return {"signal": "hold", "position": 0.0, "reason": "insufficient_data"}

        rsi_params = self.config.get("rsi_params", {})
        short_p = rsi_params.get("short_period", 9)
        long_p = rsi_params.get("long_period", 24)
        # 若未预计算则现场算
        if "rsi_9" not in data.columns:
            data = data.copy()
            data["rsi_9"] = calculate_rsi_handwrite(data["close"], short_p)
            data["rsi_24"] = calculate_rsi_handwrite(data["close"], long_p)
        if "ma50" not in data.columns:
            data = data.copy()
            data["ma50"] = calculate_ma(data["close"], 50)
        if "volume_ratio" not in data.columns:
            data = data.copy()
            data["volume_ratio"] = calculate_volume_ratio(data["volume"], 20)

        prices = data["close"]
        ma50 = data["ma50"]
        market_env = judge_market_env(prices, ma50)
        rsi_cur = data["rsi_9"].iloc[-1]
        if check_extreme_market(rsi=rsi_cur):
            return {"signal": "hold", "position": 0.0, "reason": "extreme_market"}

        sig = generate_signal_dict(data, market_env)
        pos = sig.get("position", 0.0)
        sig["position"] = apply_position_cap(pos, market_env)
        return sig

    def calculate_risk(self, signal: Dict[str, Any], data: pd.DataFrame) -> Dict[str, Any]:
        if data.empty:
            return {"stop_loss": 0.0, "take_profit": 0.0}
        close = data["close"].iloc[-1]
        rc = self.config.get("risk_control", {})
        stop_r = rc.get("stop_loss_ratio", 0.03)
        take_r = rc.get("take_profit_ratio", 0.07)
        is_lev = rc.get("is_leverage_etf", False)
        return get_stop_loss_take_profit(
            close,
            signal.get("signal", "hold"),
            is_leverage_etf=is_lev,
            stop_ratio=stop_r,
            take_ratio=take_r,
        )
