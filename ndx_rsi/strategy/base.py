"""策略抽象接口：generate_signal、calculate_risk。"""
from abc import ABC, abstractmethod
from typing import Any, Dict

import pandas as pd


class BaseTradingStrategy(ABC):
    def __init__(self, strategy_config: dict) -> None:
        self.config = strategy_config

    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> Dict[str, Any]:
        """输入含 close/volume/rsi_short/rsi_long/ma50/volume_ratio 的 DataFrame；输出 signal dict。"""
        pass

    @abstractmethod
    def calculate_risk(self, signal: Dict[str, Any], data: pd.DataFrame) -> Dict[str, Any]:
        """返回 stop_loss、take_profit 等。"""
        pass
