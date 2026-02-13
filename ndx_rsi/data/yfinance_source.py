"""
YFinance 数据源实现：拉取 NDX/QQQ/TQQQ 等日线或分钟线，列名统一小写，优先前复权。
"""
import time
from typing import Optional

import pandas as pd

from ndx_rsi.data.base import BaseDataSource


# yfinance interval: 1m, 2m, 5m, 15m, 30m, 60m, 1d, 5d, 1wk, 1mo
_FREQ_TO_INTERVAL = {"1d": "1d", "30m": "30m", "1h": "1h", "1w": "1wk", "1wk": "1wk"}


def _fetch_hist_with_retry(
    ticker, start_date: str, end_date: str, interval: str, symbol: str, max_retries: int = 2
) -> pd.DataFrame:
    """拉取 history，遇 yfinance 内部 None/异常时重试，避免二次请求限流或瞬时故障报错。"""
    import yfinance as yf

    last_err = None
    for attempt in range(max_retries):
        try:
            hist = ticker.history(start=start_date, end=end_date, interval=interval)
            if hist is not None and not hist.empty:
                return hist
            if attempt < max_retries - 1:
                time.sleep(1.5)
        except (TypeError, KeyError, AttributeError) as e:
            last_err = e
            if attempt < max_retries - 1:
                time.sleep(1.5)
    # 用 download 兜底（部分环境下更稳定）
    try:
        df = yf.download(symbol, start=start_date, end=end_date, interval=interval, progress=False, auto_adjust=True)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
            return df
    except Exception:
        pass
    if last_err is not None:
        raise RuntimeError(
            "Yahoo Finance 返回异常或空数据（可能被限流或网络波动），请稍后重试。"
        ) from last_err
    return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])


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
        hist = _fetch_hist_with_retry(ticker, start_date, end_date, interval, symbol=code)
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
