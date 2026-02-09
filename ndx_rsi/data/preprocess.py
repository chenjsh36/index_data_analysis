"""
数据预处理：缺失值策略、量能比计算、列名统一；与 TDD 2.7 一致。
"""
import pandas as pd
from typing import Tuple


# 量能比异常上限：比值 > VOLUME_RATIO_CAP 时截断
VOLUME_RATIO_CAP = 3.0
# 日线缺失连续超过此周期则标记异常
MAX_MISSING_DAYS = 2
VOLUME_MA_WINDOW = 20


def preprocess_ohlcv(df: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    """
    对 OHLCV DataFrame 做预处理：
    - 计算 volume_ratio = volume / rolling(20).mean()，>3 时截断为 VOLUME_RATIO_CAP
    - 日线缺失：若最近连续缺失 > MAX_MISSING_DAYS 则返回 is_ok=False
    返回 (预处理后的 DataFrame, is_ok)。
    """
    if df.empty or len(df) < VOLUME_MA_WINDOW:
        return df.copy(), False

    out = df.copy()
    # 列名统一小写
    out.columns = [c.lower() for c in out.columns]
    if "volume" not in out.columns:
        return out, False

    vol = out["volume"]
    vol_ma = vol.rolling(window=VOLUME_MA_WINDOW, min_periods=1).mean()
    out["volume_ratio"] = vol / vol_ma.replace(0, 1e-10)
    out.loc[out["volume_ratio"] > VOLUME_RATIO_CAP, "volume_ratio"] = VOLUME_RATIO_CAP

    # 简单缺失检查：最后几行是否有 NaN（仅看 close）
    if "close" in out.columns:
        last = out["close"].tail(MAX_MISSING_DAYS + 1)
        is_ok = last.notna().all()
    else:
        is_ok = True

    return out, bool(is_ok)
