"""策略工厂：从 config/strategy.yaml 按名称创建策略实例。"""
from ndx_rsi.config_loader import get_strategy_config
from ndx_rsi.strategy.base import BaseTradingStrategy
from ndx_rsi.strategy.ema_cross import (
    EMACrossoverV1Strategy,
    EMATrendV2Strategy,
    EMATrendV3Strategy,
)
from ndx_rsi.strategy.ndx_short import NDXShortTermRSIStrategy
from ndx_rsi.strategy.ndx_ma50_volume_rsi import NDXMA50VolumeRSIStrategy


def create_strategy(strategy_name: str) -> BaseTradingStrategy:
    """根据策略名加载配置并返回策略实例。"""
    config = get_strategy_config(strategy_name)
    if not config:
        raise ValueError(f"Unknown strategy: {strategy_name}")
    if strategy_name == "EMA_cross_v1":
        return EMACrossoverV1Strategy(config)
    if strategy_name == "EMA_trend_v2":
        return EMATrendV2Strategy(config)
    if strategy_name == "EMA_trend_v3":
        return EMATrendV3Strategy(config)
    if strategy_name == "NDX_short_term":
        return NDXShortTermRSIStrategy(config)
    if strategy_name == "NDX_MA50_Volume_RSI":
        return NDXMA50VolumeRSIStrategy(config)
    # 预留：SPX_mid_term 等
    if config.get("period_type") == "short" or "NDX" in config.get("index_code", ""):
        return NDXShortTermRSIStrategy(config)
    return NDXShortTermRSIStrategy(config)


class StrategyFactory:
    """策略工厂类，与 TDD 接口一致。"""

    @staticmethod
    def create_strategy(strategy_name: str) -> BaseTradingStrategy:
        return create_strategy(strategy_name)
