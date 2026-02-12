"""
EMA 策略：与 nasdaq_v1 逻辑一致。
- v1: 50/200 EMA 黄金/死亡交叉 + 可选月度调仓 + 止损由 runner 执行
- v2: 80/200 EMA 趋势 + 20 日波动率过滤，仅在上升趋势+低波动时持仓
"""
from typing import Any, Dict, Optional

import pandas as pd

from ndx_rsi.strategy.base import BaseTradingStrategy


def _ensure_ema_columns(df: pd.DataFrame, short: int, long: int) -> None:
    """若列不存在则计算 EMA（就地修改 df 的 copy 由调用方负责）。"""
    short_col = f"ema_{short}"
    long_col = f"ema_{long}"
    if short_col not in df.columns and "close" in df.columns:
        df[short_col] = df["close"].ewm(span=short, adjust=False).mean()
    if long_col not in df.columns and "close" in df.columns:
        df[long_col] = df["close"].ewm(span=long, adjust=False).mean()


class EMACrossoverV1Strategy(BaseTradingStrategy):
    """EMA 交叉策略 v1：黄金交叉买入、死亡交叉卖出，支持日线/月度调仓。"""

    def generate_signal(
        self, data: pd.DataFrame, current_position_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if data.empty or len(data) < 2:
            return {"signal": "hold", "position": 0.0, "reason": "insufficient_data"}
        short_ema = self.config.get("short_ema", 50)
        long_ema = self.config.get("long_ema", 200)
        rebalance_freq = self.config.get("rebalance_freq", "daily")
        data = data.copy()
        _ensure_ema_columns(data, short_ema, long_ema)
        ema_short_col = f"ema_{short_ema}"
        ema_long_col = f"ema_{long_ema}"
        if ema_short_col not in data.columns or ema_long_col not in data.columns:
            return {"signal": "hold", "position": 0.0, "reason": "missing_ema"}
        row = data.iloc[-1]
        prev = data.iloc[-2]
        cur_short = row[ema_short_col]
        cur_long = row[ema_long_col]
        prev_short = prev[ema_short_col]
        prev_long = prev[ema_long_col]
        # 月度调仓：仅当月最后一个交易日根据 EMA 决定仓位
        if rebalance_freq == "monthly":
            period = data.index[-1].to_period("M")
            same_month = data.index[data.index.to_period("M") == period]
            is_month_end = len(same_month) > 0 and data.index[-1] == same_month[-1]
            if is_month_end:
                position = 1.0 if cur_short > cur_long else 0.0
                reason = "monthly_rebalance_bull" if position else "monthly_rebalance_bear"
                return {"signal": "buy" if position else "sell", "position": position, "reason": reason}
            # 非月末：维持当前仓位
            if current_position_info and current_position_info.get("direction") == "long":
                return {"signal": "hold", "position": 1.0, "reason": "hold_until_month_end"}
            return {"signal": "hold", "position": 0.0, "reason": "hold_until_month_end"}
        # 日线：黄金/死亡交叉
        golden = cur_short > cur_long and prev_short <= prev_long
        death = cur_short < cur_long and prev_short >= prev_long
        if golden:
            return {"signal": "buy", "position": 1.0, "reason": "golden_cross"}
        if death:
            return {"signal": "sell", "position": 0.0, "reason": "death_cross"}
        # 维持
        if current_position_info and current_position_info.get("direction") == "long":
            return {"signal": "hold", "position": 1.0, "reason": "hold"}
        return {"signal": "hold", "position": 0.0, "reason": "hold"}

    def calculate_risk(self, signal: Dict[str, Any], data: pd.DataFrame) -> Dict[str, Any]:
        if data.empty:
            return {"stop_loss": 0.0, "take_profit": 0.0}
        close = float(data["close"].iloc[-1])
        rc = self.config.get("risk_control", {})
        stop_r = rc.get("stop_loss_ratio", self.config.get("stop_loss_ratio", 0.05))
        take_r = rc.get("take_profit_ratio", 0.20)
        return {
            "stop_loss": close * (1 - stop_r),
            "take_profit": close * (1 + take_r),
        }


class EMATrendV2Strategy(BaseTradingStrategy):
    """趋势增强 v2：80/200 EMA 定趋势 + 20 日波动率过滤，仅上升+低波动时持仓。"""

    def generate_signal(
        self, data: pd.DataFrame, current_position_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if data.empty or len(data) < 2:
            return {"signal": "hold", "position": 0.0, "reason": "insufficient_data"}
        fast = self.config.get("ema_fast", 80)
        slow = self.config.get("ema_slow", 200)
        vol_window = self.config.get("vol_window", 20)
        vol_threshold = self.config.get("vol_threshold", 0.02)
        ema_fast_col = f"ema_{fast}"
        ema_slow_col = f"ema_{slow}"
        vol_col = f"vol_{vol_window}"
        if ema_fast_col not in data.columns or ema_slow_col not in data.columns or vol_col not in data.columns:
            return {"signal": "hold", "position": 0.0, "reason": "missing_indicators"}
        row = data.iloc[-1]
        uptrend = row[ema_fast_col] > row[ema_slow_col]
        low_vol = row[vol_col] < vol_threshold
        position = 1.0 if (uptrend and low_vol) else 0.0
        reason = "uptrend_low_vol" if position else "no_uptrend_or_high_vol"
        return {"signal": "buy" if position else "sell", "position": position, "reason": reason}

    def calculate_risk(self, signal: Dict[str, Any], data: pd.DataFrame) -> Dict[str, Any]:
        if data.empty:
            return {"stop_loss": 0.0, "take_profit": 0.0}
        close = float(data["close"].iloc[-1])
        rc = self.config.get("risk_control", {})
        stop_r = rc.get("stop_loss_ratio", 0.05)
        take_r = rc.get("take_profit_ratio", 0.20)
        return {
            "stop_loss": close * (1 - stop_r),
            "take_profit": close * (1 + take_r),
        }
