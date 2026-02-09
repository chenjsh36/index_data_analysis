"""量能比：当日成交量 / 近 window 日均量。"""
import pandas as pd

DEFAULT_WINDOW = 20


def calculate_volume_ratio(volume: pd.Series, window: int = DEFAULT_WINDOW) -> pd.Series:
    """volume / rolling(volume).mean()，避免除零。"""
    vol_ma = volume.rolling(window=window, min_periods=1).mean().replace(0, 1e-10)
    return volume / vol_ma
