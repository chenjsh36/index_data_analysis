"""
YFinance 数据源实现：拉取 NDX/QQQ/TQQQ 等日线或分钟线，列名统一小写，优先前复权。
"""
from typing import Optional

import pandas as pd

from ndx_rsi.data.base import BaseDataSource


# yfinance interval: 1m, 2m, 5m, 15m, 30m, 60m, 1d, 5d, 1wk, 1mo
_FREQ_TO_INTERVAL = {"1d": "1d", "30m": "30m", "1h": "1h", "1w": "1wk", "1wk": "1wk"}


class YFinanceDataSource(BaseDataSource):
    """使用 yfinance 拉取行情，列名统一为 open/high/low/close/volume，索引 DatetimeIndex。"""

    def get_historical_data(
        self,
        start_date: str,
        end_date: str,
        frequency: str = "1d",
    ) -> pd.DataFrame:
        import yfinance as yf

        interval = _FREQ_TO_INTERVAL.get(frequency, "1d")
        code = self.config.get("code", self.index_code)
        ticker = yf.Ticker(code)
        hist = ticker.history(start=start_date, end=end_date, interval=interval)
        if hist.empty:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

        # 列名统一小写；优先 Adj Close 作为 close（前复权）
        cols = ["Open", "High", "Low", "Close", "Volume"]
        if "Adj Close" in hist.columns:
            hist = hist.copy()
            hist["Close"] = hist["Adj Close"]
        hist = hist[[c for c in cols if c in hist.columns]]
        hist.columns = [c.lower() for c in hist.columns]
        hist.index = pd.to_datetime(hist.index)
        hist = hist.sort_index()
        return hist

    def get_realtime_data(self) -> pd.DataFrame:
        """拉取最近一段历史作为“实时”数据（yfinance 无真正实时，用近期数据代替）。"""
        import datetime

        end = datetime.date.today()
        start = end - datetime.timedelta(days=120)
        return self.get_historical_data(
            start.isoformat(), end.isoformat(), frequency="1d"
        )
