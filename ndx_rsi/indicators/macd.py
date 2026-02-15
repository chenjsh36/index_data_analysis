"""
MACD (12, 26, 9) 手写实现。
公式：EMA12、EMA26，macd_line = EMA12 - EMA26，signal_line = EMA(macd_line, 9)，histogram = macd_line - signal_line。
用于 v7 纳指机构级策略：macd_line > 0 为多头。
"""
import pandas as pd


def calculate_macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    计算 MACD。返回 (macd_line, signal_line, histogram)。
    策略仅用 macd_line 做 0 轴判断。
    """
    if close.empty or len(close) < slow:
        return (
            pd.Series(index=close.index, dtype=float),
            pd.Series(index=close.index, dtype=float),
            pd.Series(index=close.index, dtype=float),
        )
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram
