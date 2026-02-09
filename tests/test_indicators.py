"""T4/T5：RSI/MA/量能比/市场环境。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd
import pytest
from ndx_rsi.indicators import (
    calculate_rsi_handwrite,
    calculate_ma,
    calculate_volume_ratio,
    verify_rsi,
    judge_market_env,
    get_rsi_thresholds,
)


@pytest.fixture
def sample_prices():
    np.random.seed(42)
    return pd.Series(100 + np.cumsum(np.random.randn(100) * 2), index=pd.date_range("2024-01-01", periods=100, freq="D"))


def test_rsi_handwrite_shape(sample_prices):
    rsi = calculate_rsi_handwrite(sample_prices, 14)
    assert len(rsi) == len(sample_prices)
    assert rsi.dropna().between(0, 100).all()


def test_verify_rsi_returns_bool(sample_prices):
    out = verify_rsi(sample_prices, 14, max_diff=0.1)
    assert isinstance(out, bool)


def test_calculate_ma(sample_prices):
    ma = calculate_ma(sample_prices, 50)
    assert len(ma) == len(sample_prices)
    assert ma.iloc[-1] == pytest.approx(sample_prices.tail(50).mean(), rel=1e-5)


def test_volume_ratio():
    vol = pd.Series([1e6] * 25, index=pd.date_range("2024-01-01", periods=25, freq="D"))
    vr = calculate_volume_ratio(vol, 20)
    assert len(vr) == 25
    assert vr.iloc[-1] == pytest.approx(1.0, rel=1e-5)


def test_judge_market_env_returns_string(sample_prices):
    ma50 = calculate_ma(sample_prices, 50)
    env = judge_market_env(sample_prices, ma50)
    assert env in ("bull", "bear", "oscillate", "transition")


def test_get_rsi_thresholds():
    th = get_rsi_thresholds("bull")
    assert th["overbuy"] == 80 and th["oversell"] == 40
    th = get_rsi_thresholds("oscillate")
    assert th["overbuy"] == 70 and th["oversell"] == 30
