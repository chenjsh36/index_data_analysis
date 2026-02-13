"""
配置加载：从 config/datasource.yaml、config/strategy.yaml 按 key 读取配置。
仅负责加载与返回 dict，无业务逻辑。
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


def _config_dir() -> Path:
    """项目 config 目录：优先环境变量 NDX_RSI_CONFIG，否则为包所在目录的上级/config。"""
    env = os.environ.get("NDX_RSI_CONFIG")
    if env:
        return Path(env)
    # 包路径 ndx_rsi/__init__.py -> 上级 -> config
    pkg = Path(__file__).resolve().parent
    return pkg.parent / "config"


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    if yaml is None:
        raise ImportError("PyYAML is required. Install with: pip install PyYAML")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_datasource_config(index_code: Optional[str] = None) -> Dict[str, Any]:
    """
    读取 datasource 配置。若提供 index_code，返回该指数配置 dict；否则返回全量 indices。
    """
    path = _config_dir() / "datasource.yaml"
    data = _load_yaml(path)
    indices = data.get("indices", {})
    if index_code is not None:
        return indices.get(index_code, {})
    return indices


def get_strategy_config(strategy_name: Optional[str] = None) -> Dict[str, Any]:
    """
    读取 strategy 配置。若提供 strategy_name，返回该策略配置 dict；否则返回全量 strategies。
    """
    path = _config_dir() / "strategy.yaml"
    data = _load_yaml(path)
    strategies = data.get("strategies", {})
    if strategy_name is not None:
        return strategies.get(strategy_name, {})
    return strategies


def get_backtest_config() -> Dict[str, Any]:
    """
    读取回测配置（v2）。从 config/strategy.yaml 的 backtest 段加载，缺失项用默认值。
    返回结构见 docs/v2/04-technical-design.md §2.4。
    """
    path = _config_dir() / "strategy.yaml"
    data = _load_yaml(path) if path.exists() else {}
    raw = data.get("backtest", {})
    cb = raw.get("circuit_breaker", {})
    metrics = raw.get("metrics", {})
    return {
        "use_stop_loss_take_profit": raw.get("use_stop_loss_take_profit", True),
        "next_day_execution": raw.get("next_day_execution", False),
        "use_ma50_exit": raw.get("use_ma50_exit", False),
        "circuit_breaker": {
            "enabled": cb.get("enabled", False),
            "drawdown_threshold": cb.get("drawdown_threshold", 0.10),
            "position_after": cb.get("position_after", 0.30),
            "cooldown_bars": cb.get("cooldown_bars", 2),
        },
        "metrics": {
            "risk_free_rate": metrics.get("risk_free_rate", 0.0),
            "accrue_risk_free_when_flat": metrics.get("accrue_risk_free_when_flat", True),
        },
        "commission": raw.get("commission", 0.0005),
    }
