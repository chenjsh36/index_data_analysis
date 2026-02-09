"""
数据源抽象接口：按标的与时间范围获取行情（OHLCV），屏蔽具体数据源。
"""
from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd


class BaseDataSource(ABC):
    """
    所有数据源的统一抽象接口。
    返回 DataFrame 列至少含：open, high, low, close, volume；索引为 DatetimeIndex。
    """

    def __init__(self, index_code: str, config: dict) -> None:
        self.index_code = index_code
        self.config = config

    @abstractmethod
    def get_historical_data(
        self,
        start_date: str,
        end_date: str,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        """获取指定区间的历史行情。"""
        pass

    @abstractmethod
    def get_realtime_data(self) -> pd.DataFrame:
        """获取最新一段数据（用于信号生成）。"""
        pass
