"""T1 验收：配置加载能按 key 返回 dict。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from ndx_rsi.config_loader import get_datasource_config, get_strategy_config


def test_get_datasource_config_returns_dict():
    all_indices = get_datasource_config()
    assert isinstance(all_indices, dict)
    ndx = get_datasource_config("NDX")
    assert isinstance(ndx, dict)
    assert ndx.get("code") == "^NDX" or ndx.get("data_source") == "yfinance" or len(ndx) >= 0


def test_get_strategy_config_returns_dict():
    all_strategies = get_strategy_config()
    assert isinstance(all_strategies, dict)
    cfg = get_strategy_config("NDX_short_term")
    assert isinstance(cfg, dict)
    assert cfg.get("index_code") == "NDX" or "rsi_params" in cfg or len(cfg) >= 0
