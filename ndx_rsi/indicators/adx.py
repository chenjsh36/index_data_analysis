"""
ADX (Average Directional Index) 14 日，手写实现。
公式：+DM/-DM、TR → Wilder 平滑 → +DI/-DI → DX → ADX。
用于 v7 纳指机构级策略：ADX > 25 为强趋势。
"""
import pandas as pd
import numpy as np


def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    """Wilder 平滑：首值为前 period 的 SMA，之后 RMA_t = (RMA_{t-1} * (period-1) + x_t) / period。"""
    out = pd.Series(index=series.index, dtype=float)
    arr = series.values
    n = len(arr)
    if n < period:
        return out
    # 第一个有效值：前 period 的简单平均
    out.iloc[period - 1] = np.nanmean(arr[:period])
    for i in range(period, n):
        prev = out.iloc[i - 1]
        if pd.isna(prev):
            out.iloc[i] = np.nan
        else:
            out.iloc[i] = (prev * (period - 1) + arr[i]) / period
    return out


def calculate_adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    计算 ADX（14 日）。需 high、low、close 同长度同索引。
    返回与 close 同索引的 Series，前约 2*period 行为 NaN（TR/+DM/-DM 平滑后再算 DX 再平滑）。
    """
    if len(close) < 2 or len(high) != len(close) or len(low) != len(close):
        return pd.Series(index=close.index, dtype=float)

    high_prev = high.shift(1)
    low_prev = low.shift(1)
    close_prev = close.shift(1)

    # TR = max(high-low, |high-close_prev|, |low-close_prev|)
    tr = pd.concat([
        high - low,
        (high - close_prev).abs(),
        (low - close_prev).abs(),
    ], axis=1).max(axis=1)

    # +DM, -DM：仅保留较大一方，且为正值
    up_move = high - high_prev
    down_move = low_prev - low
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    plus_dm = pd.Series(plus_dm, index=close.index)
    minus_dm = pd.Series(minus_dm, index=close.index)

    # Wilder 平滑
    atr = _wilder_smooth(tr, period)
    plus_di_smooth = _wilder_smooth(plus_dm, period)
    minus_di_smooth = _wilder_smooth(minus_dm, period)

    # +DI, -DI（避免除零）
    atr_safe = atr.replace(0, np.nan)
    plus_di = 100.0 * plus_di_smooth / atr_safe
    minus_di = 100.0 * minus_di_smooth / atr_safe

    # DX = 100 * |+DI - -DI| / (+DI + -DI)
    di_sum = plus_di + minus_di
    di_sum = di_sum.replace(0, np.nan)
    dx = 100.0 * (plus_di - minus_di).abs() / di_sum

    # ADX = Wilder smooth of DX
    adx = _wilder_smooth(dx, period)
    return adx
