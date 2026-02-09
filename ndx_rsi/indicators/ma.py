"""简单移动平均（SMA），用于 MA50、20 日均量等。"""
import pandas as pd


def calculate_ma(series: pd.Series, window: int) -> pd.Series:
    """SMA(series, window)。"""
    return series.rolling(window=window, min_periods=1).mean()


def calculate_ma5(series: pd.Series) -> pd.Series:
    """SMA(series, 5)，与 rolling(5).mean() 一致。TASK-07 金叉/死叉 MA5 确认。"""
    return series.rolling(window=5, min_periods=1).mean()


def calculate_ma20(series: pd.Series) -> pd.Series:
    """SMA(series, 20)，与 rolling(20).mean() 一致。TASK-13 下降趋势超卖可选增强。"""
    return series.rolling(window=20, min_periods=1).mean()
