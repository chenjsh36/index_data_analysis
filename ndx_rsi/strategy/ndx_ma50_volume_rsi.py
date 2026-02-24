"""
NDX 50日均线+成交量+RSI 三合一策略：趋势与信号规则完全按 BRD（docs/v8/brd.md）执行。
BRD 第三步：趋势判定（上升/下降/震荡/趋势过渡）；第四步：RSI(14)+volume_ratio 信号。
"""
from typing import Any, Dict, Optional

import pandas as pd

from ndx_rsi.strategy.base import BaseTradingStrategy


# 趋势类型与 BRD 伪代码一致
TREND_UP = "上升趋势"
TREND_DOWN = "下降趋势"
TREND_OSCILLATE = "震荡趋势"
TREND_TRANSITION = "趋势过渡（无明确方向）"

# 最小 K 线数：需满足 50 日 MA50、连续 3 日方向、连续 5 日斜率
MIN_BARS = 60


def _sma50_slope_pct(ma50: pd.Series, i: int) -> Optional[float]:
    """SMA50 斜率百分比：(ma50[i]-ma50[i-1])/ma50[i-1]*100。"""
    if i < 1 or i >= len(ma50):
        return None
    prev = float(ma50.iloc[i - 1])
    if prev == 0 or pd.isna(prev):
        return None
    cur = float(ma50.iloc[i])
    if pd.isna(cur):
        return None
    return (cur - prev) / prev * 100.0


def _get_trend_type(df: pd.DataFrame, i: int, config: dict) -> str:
    """
    BRD 第三步：趋势判定。
    上升 > 下降 > 震荡 > 趋势过渡。
    """
    if i < 3 or "close" not in df.columns or "ma50" not in df.columns:
        return TREND_TRANSITION
    close = df["close"].iloc
    ma50 = df["ma50"].iloc
    slope_th = config.get("slope_flat_threshold", 0.1)  # 0.1 = 0.1%
    osc_range = config.get("oscillate_range", 0.03)

    c_i = float(close[i])
    m_i = float(ma50[i])
    m_i1 = float(ma50[i - 1])
    m_i2 = float(ma50[i - 2])
    m_i3 = float(ma50[i - 3])
    if pd.isna(c_i) or pd.isna(m_i) or pd.isna(m_i1) or pd.isna(m_i2) or pd.isna(m_i3):
        return TREND_TRANSITION
    c_i1 = float(close[i - 1])
    m_i1_val = float(ma50[i - 1])

    # 上升趋势
    cond_up_1 = c_i > m_i
    cond_up_2 = (m_i > m_i1) and (m_i1 > m_i2) and (m_i2 > m_i3)
    cond_up_3 = not ((c_i < m_i) and (c_i1 < m_i1_val))
    if cond_up_1 and cond_up_2 and cond_up_3:
        return TREND_UP

    # 下降趋势
    cond_down_1 = c_i < m_i
    cond_down_2 = (m_i < m_i1) and (m_i1 < m_i2) and (m_i2 < m_i3)
    cond_down_3 = not ((c_i > m_i) and (c_i1 > m_i1_val))
    if cond_down_1 and cond_down_2 and cond_down_3:
        return TREND_DOWN

    # 震荡：连续 5 日斜率绝对值 < slope_th，且收盘在 SMA50±osc_range
    if i < 4:
        return TREND_TRANSITION
    all_slope_flat = True
    for k in range(5):
        slope = _sma50_slope_pct(df["ma50"], i - k)
        if slope is None or abs(slope) >= slope_th:
            all_slope_flat = False
            break
    if not all_slope_flat:
        return TREND_TRANSITION
    if m_i <= 0:
        return TREND_TRANSITION
    band_lo = m_i * (1 - osc_range)
    band_hi = m_i * (1 + osc_range)
    if band_lo <= c_i <= band_hi:
        return TREND_OSCILLATE
    return TREND_TRANSITION


class NDXMA50VolumeRSIStrategy(BaseTradingStrategy):
    """纳指 50日均线+成交量+RSI 三合一策略；趋势与信号完全按 BRD 执行。"""

    def generate_signal(
        self, data: pd.DataFrame, current_position_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if data.empty or len(data) < MIN_BARS:
            return {
                "signal": "hold",
                "position": 0.0,
                "reason": "insufficient_data",
                "trend_type": TREND_TRANSITION,
                "operation": "观望",
            }
        for col in ("ma50", "rsi_14", "volume_ratio"):
            if col not in data.columns:
                return {
                    "signal": "hold",
                    "position": 0.0,
                    "reason": "missing_indicators",
                    "trend_type": TREND_TRANSITION,
                    "operation": "观望",
                }

        i = len(data) - 1
        trend = _get_trend_type(data, i, self.config)
        row = data.iloc[i]
        rsi14 = float(row["rsi_14"])
        vol_ratio = float(row["volume_ratio"])
        vol_heavy = self.config.get("vol_ratio_heavy", 1.2)
        vol_light = self.config.get("vol_ratio_light", 0.8)

        # BRD 第四步：按趋势分支 + RSI + 量能
        signal = "hold"
        position = 0.0
        reason = "transition"
        operation = "观望"

        if trend == TREND_UP:
            if 40 <= rsi14 <= 50 and vol_ratio <= vol_light:
                signal, position, reason = "buy", 0.35, "bull_pullback_volume_ok"
                operation = "加仓30-40%，止损MA50下方2%"
            elif 70 <= rsi14 <= 80 and vol_ratio <= vol_light:
                signal, position, reason = "sell", 0.25, "bull_overbought_volume_weak"
                operation = "轻仓减仓20-30%，不做空"
            elif rsi14 > 80 and vol_ratio >= vol_heavy:
                signal, position, reason = "hold", 1.0, "bull_overbought_volume_ok"
                operation = "继续持仓，忽略超买"
            else:
                reason = "bull_hold"
                position = 1.0  # 上升趋势默认偏多
                operation = "观望/维持"
        elif trend == TREND_DOWN:
            if 50 <= rsi14 <= 60 and vol_ratio >= vol_heavy:
                signal, position, reason = "sell", 0.5, "bear_rally_volume_heavy"
                operation = "减仓40-50%，不做多"
            elif 20 <= rsi14 <= 30 and vol_ratio <= vol_light:
                signal, position, reason = "buy", 0.3, "bear_oversold_volume_light"
                operation = "轻仓试多30%，止损MA20下方3%"
            elif rsi14 < 20 and vol_ratio >= vol_heavy:
                signal, position, reason = "hold", 0.0, "bear_oversold_no_bottom"
                operation = "观望，不抄底"
            else:
                reason = "bear_hold"
                position = 0.0
                operation = "观望"
        elif trend == TREND_OSCILLATE:
            if 65 <= rsi14 <= 70 and vol_ratio >= vol_heavy:
                signal, position, reason = "sell", 0.6, "osc_sell"
                operation = "减仓30-40%，止盈RSI回50附近"
            elif 30 <= rsi14 <= 35 and vol_ratio <= vol_light:
                signal, position, reason = "buy", 0.35, "osc_buy"
                operation = "加仓30-40%，止盈RSI回50附近"
            else:
                reason = "osc_hold"
                operation = "观望"
        else:
            reason = "transition"
            position = 0.0
            operation = "观望"

        return {
            "signal": signal,
            "position": position,
            "reason": reason,
            "trend_type": trend,
            "operation": operation,
        }

    def calculate_risk(self, signal: Dict[str, Any], data: pd.DataFrame) -> Dict[str, Any]:
        if data.empty:
            return {"stop_loss": 0.0, "take_profit": 0.0}
        row = data.iloc[-1]
        close = float(row["close"])
        rc = self.config.get("risk_control", {})
        stop_r = rc.get("stop_loss_ratio", 0.05)
        take_r = rc.get("take_profit_ratio", 0.20)
        reason = (signal.get("reason") or "").strip()

        # BRD 文案对应：部分 reason 用 MA50/MA20 下方止损
        stop_below_ma50 = self.config.get("stop_below_ma50_pct", 0.02)
        stop_below_ma20 = self.config.get("stop_below_ma20_pct", 0.03)
        stop_loss = close * (1 - stop_r)
        take_profit = close * (1 + take_r)
        if "bull_pullback" in reason and "ma50" in data.columns:
            ma50 = float(row["ma50"])
            stop_loss = ma50 * (1 - stop_below_ma50)
        if "bear_oversold_volume_light" in reason and "ma20" in data.columns:
            ma20 = float(row["ma20"])
            stop_loss = ma20 * (1 - stop_below_ma20)

        return {"stop_loss": stop_loss, "take_profit": take_profit}
