"""
回测：拉取历史数据 → 预计算指标 → 按日推进，调用策略生成信号并模拟成交，统计绩效。
首版采用自研循环（不依赖 Backtrader），便于与现有策略接口一致。
"""
import pandas as pd
from typing import Any, Dict, Optional

from ndx_rsi.data import YFinanceDataSource, preprocess_ohlcv
from ndx_rsi.config_loader import get_datasource_config
from ndx_rsi.indicators import (
    calculate_rsi_handwrite,
    calculate_ma,
    calculate_volume_ratio,
)
from ndx_rsi.strategy.factory import create_strategy


def run_backtest(
    strategy_name: str = "NDX_short_term",
    symbol: str = "QQQ",
    start_date: str = "2018-01-01",
    end_date: str = "2025-01-01",
    commission: float = 0.0005,
) -> Dict[str, Any]:
    """
    执行回测，返回绩效 dict：win_rate, profit_factor, max_drawdown, total_return, sharpe_ratio 等。
    """
    config = get_datasource_config(symbol) or get_datasource_config("QQQ")
    if not config:
        config = {"code": symbol, "data_source": "yfinance"}
    ds = YFinanceDataSource(symbol, config)
    raw = ds.get_historical_data(start_date, end_date, "1d")
    if raw.empty or len(raw) < 60:
        return {"error": "insufficient_data", "win_rate": 0, "max_drawdown": 0}

    df, _ = preprocess_ohlcv(raw)
    df["ma50"] = calculate_ma(df["close"], 50)
    df["rsi_9"] = calculate_rsi_handwrite(df["close"], 9)
    df["rsi_24"] = calculate_rsi_handwrite(df["close"], 24)
    df["volume_ratio"] = calculate_volume_ratio(df["volume"], 20)

    strategy = create_strategy(strategy_name)
    # 按日推进：从第 50 根开始有完整指标
    position = 0.0
    entries: list = []  # (date, price, side, size)
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    wins = 0
    losses = 0
    total_pnl = 0.0

    for i in range(50, len(df)):
        window = df.iloc[: i + 1]
        sig = strategy.generate_signal(window)
        risk = strategy.calculate_risk(sig, window)
        price = df["close"].iloc[i]
        date = df.index[i]
        pos_new = sig.get("position", 0.0)
        if pos_new != 0 and position == 0:
            position = pos_new
            entries.append((date, price, "buy" if pos_new > 0 else "sell", abs(pos_new)))
        elif (pos_new == 0 or (pos_new > 0 != position > 0)) and position != 0:
            # 平仓：简化按当前仓位与价格算一次 PnL
            entry_price = entries[-1][1] if entries else price
            side = 1 if position > 0 else -1
            ret = (price - entry_price) / entry_price * side
            ret -= commission * 2
            total_pnl += ret
            if ret > 0:
                wins += 1
            else:
                losses += 1
            equity *= 1 + ret
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
            position = pos_new
            if position != 0:
                entries.append((date, price, "buy" if position > 0 else "sell", abs(position)))
            else:
                entries.clear()

    total_trades = wins + losses
    win_rate = wins / total_trades if total_trades else 0
    # 简化：盈亏比用平均盈/平均亏近似
    total_return = equity - 1.0
    # 夏普：简化 (年化) 用 total_return / 年数，波动用 max_dd 近似
    years = max((pd.to_datetime(end_date) - pd.to_datetime(start_date)).days / 365, 0.1)
    ann_return = total_return / years
    sharpe = ann_return / (max_dd + 1e-8) if max_dd else 0

    return {
        "win_rate": round(win_rate, 4),
        "total_trades": total_trades,
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_dd, 4),
        "sharpe_ratio": round(sharpe, 4),
        "profit_factor": round(win_rate / (1 - win_rate), 4) if win_rate < 1 else 99,
    }
