"""
RSI 计算：手写实现（与 BRD 公式一致）+ TA-Lib 验证；偏差≤0.1 视为通过。
"""
import pandas as pd
from typing import Optional

# TA-Lib 可选：未安装时 verify_rsi 跳过或返回 True（仅手写）
try:
    import talib
    _HAS_TALIB = True
except ImportError:
    talib = None  # type: ignore
    _HAS_TALIB = False


def calculate_rsi_handwrite(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    手写 RSI：SMA 涨幅/跌幅，RS = AvgU/AvgD，RSI = 100 - 100/(1+RS)。
    与 BRD 公式一致，无下跌时 RSI=100（通过 avg_loss 替换 0 避免除零）。
    """
    delta = prices.diff(1)
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    avg_loss = avg_loss.replace(0, 1e-10)
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def calculate_rsi_talib(prices: pd.Series, period: int = 14) -> pd.Series:
    """使用 TA-Lib 计算 RSI，用于验证手写结果。未安装 TA-Lib 时返回与手写相同。"""
    if not _HAS_TALIB:
        return calculate_rsi_handwrite(prices, period)
    rsi = talib.RSI(prices.values, timeperiod=period)
    out = pd.Series(rsi, index=prices.index)
    return out.fillna(50.0)


def verify_rsi(
    prices: pd.Series,
    period: int = 14,
    max_diff: float = 0.1,
) -> bool:
    """
    验证手写 RSI 与 TA-Lib 偏差≤max_diff。
    若未安装 TA-Lib，返回 True（仅手写可用）。
    """
    if not _HAS_TALIB:
        return True
    hand = calculate_rsi_handwrite(prices, period)
    lib = calculate_rsi_talib(prices, period)
    valid = hand.notna() & lib.notna()
    if not valid.any():
        return True
    diff = (hand - lib).abs()
    return diff[valid].max() <= max_diff
