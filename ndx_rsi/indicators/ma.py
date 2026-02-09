"""简单移动平均（SMA），用于 MA50、20 日均量等。"""
import pandas as pd


def calculate_ma(series: pd.Series, window: int) -> pd.Series:
    """SMA(series, window)。"""
    return series.rolling(window=window, min_periods=1).mean()
