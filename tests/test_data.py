"""T2/T3：数据层拉取与预处理。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import pytest
from ndx_rsi.data import YFinanceDataSource, preprocess_ohlcv


@pytest.fixture
def ds():
    return YFinanceDataSource("QQQ", {"code": "QQQ"})


def test_yfinance_historical_returns_dataframe(ds):
    df = ds.get_historical_data("2024-06-01", "2024-08-01", "1d")
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    for col in ["open", "high", "low", "close", "volume"]:
        assert col in df.columns
    assert hasattr(df.index, "strftime") or len(df.index) > 0


def test_preprocess_adds_volume_ratio():
    raw = pd.DataFrame({
        "close": [100.0] * 25,
        "volume": [1e6] * 25,
    })
    raw.index = pd.date_range("2024-01-01", periods=25, freq="D")
    df, ok = preprocess_ohlcv(raw)
    assert "volume_ratio" in df.columns
    assert ok is True
