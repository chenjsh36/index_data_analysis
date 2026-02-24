"""
回测：拉取历史数据 → 预计算指标 → 按日推进，调用策略生成信号并模拟成交，统计绩效。
默认回测区间与 nasdaq_v1 一致：2003-01-01 至今日。
v2: Bar 内止损/止盈、可选趋势破位、回撤熔断、标准绩效指标（profit_factor、sharpe）。

run_backtest 受 config/strategy.yaml 影响：
  【直接】backtest 段（get_backtest_config()）：
    - use_stop_loss_take_profit  是否 Bar 内检查止损/止盈
    - use_ma50_exit              是否趋势破位（收盘与 MA50）平仓
    - circuit_breaker.enabled / drawdown_threshold / position_after / cooldown_bars
    - metrics.risk_free_rate     夏普计算用无风险利率；空仓计息时也使用该年化利率按日复利
    - metrics.accrue_risk_free_when_flat  空仓时是否按无风险利率对权益计息（默认 true，见 docs/v4/06-backtest-cash-risk-free-accrual.md）
    - next_day_execution         T 日信号 T+1 日执行（true=次日执行，与 nasdaq_v1 一致）
    - commission                 手续费比例
  【间接】strategies.<strategy_name> 段（策略 generate_signal / calculate_risk）：
    - risk_control.stop_loss_ratio / take_profit_ratio  决定每笔开仓的止损/止盈价
    - risk_control.is_leverage_etf
    - rsi_params / use_divergence 等  决定信号与仓位，进而影响开平仓与 PnL
"""
import math
import datetime as dt

import pandas as pd
from typing import Any, Dict, List, Optional, Tuple, Union

from ndx_rsi.data import YFinanceDataSource, preprocess_ohlcv
from ndx_rsi.config_loader import get_datasource_config, get_backtest_config, get_strategy_config
from ndx_rsi.indicators import (
    calculate_rsi_handwrite,
    calculate_ma,
    calculate_ma5,
    calculate_ma20,
    calculate_volume_ratio,
    calculate_adx,
    calculate_macd,
)
from ndx_rsi.strategy.factory import create_strategy


def run_backtest(
    strategy_name: str = "NDX_short_term",
    symbol: str = "QQQ",
    start_date: str = "2003-01-01",
    end_date: Optional[str] = None,
    commission: Optional[float] = None,
    return_series: bool = False,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], pd.DataFrame]]:
    """
    执行回测，返回绩效 dict：win_rate, profit_factor, max_drawdown, total_return, sharpe_ratio 等。
    v2: profit_factor = 总盈利/总亏损，sharpe = (年化收益 - 无风险)/收益标准差；支持 Bar 内止损止盈与回撤熔断。
    v4: return_series=True 时返回 (result_dict, series_df)，series_df 含 equity, strategy_cum_return, benchmark_cum_return, position。
    """
    if end_date is None:
        end_date = dt.date.today().isoformat()
    bt_cfg = get_backtest_config()
    if commission is None:
        commission = bt_cfg.get("commission", 0.0005)
    use_sl_tp = bt_cfg.get("use_stop_loss_take_profit", True)
    next_day_execution = bt_cfg.get("next_day_execution", False)
    use_ma50_exit = bt_cfg.get("use_ma50_exit", False)
    cb = bt_cfg.get("circuit_breaker", {})
    cb_enabled = cb.get("enabled", False)
    cb_threshold = cb.get("drawdown_threshold", 0.10)
    cb_position_after = cb.get("position_after", 0.30)
    cb_cooldown_bars = cb.get("cooldown_bars", 2)
    metrics_cfg = bt_cfg.get("metrics", {})
    risk_free_rate = metrics_cfg.get("risk_free_rate", 0.0)
    accrue_risk_free_when_flat = metrics_cfg.get("accrue_risk_free_when_flat", True)
    # 日化无风险利率（复利），空仓计息时使用
    rfr_daily = (1.0 + float(risk_free_rate)) ** (1.0 / 252) - 1.0

    config = get_datasource_config(symbol) or get_datasource_config("QQQ")
    if not config:
        config = {"code": symbol, "data_source": "yfinance"}
    ds = YFinanceDataSource(symbol, config)
    raw = ds.get_historical_data(start_date, end_date, "1d")
    if raw.empty or len(raw) < 60:
        return {"error": "insufficient_data", "win_rate": 0, "max_drawdown": 0}

    df, _ = preprocess_ohlcv(raw)
    strategy = create_strategy(strategy_name)
    loop_start = 50
    if strategy_name == "EMA_cross_v1":
        sc = get_strategy_config(strategy_name) or {}
        short_ema = sc.get("short_ema", 50)
        long_ema = sc.get("long_ema", 200)
        df["ema_" + str(short_ema)] = df["close"].ewm(span=short_ema, adjust=False).mean()
        df["ema_" + str(long_ema)] = df["close"].ewm(span=long_ema, adjust=False).mean()
        loop_start = max(50, long_ema)
        if len(df) < loop_start:
            return {"error": "insufficient_data", "win_rate": 0, "max_drawdown": 0}
    elif strategy_name == "EMA_trend_v2":
        sc = get_strategy_config(strategy_name) or {}
        ema_fast = sc.get("ema_fast", 80)
        ema_slow = sc.get("ema_slow", 200)
        vol_window = sc.get("vol_window", 20)
        df["ema_" + str(ema_fast)] = df["close"].ewm(span=ema_fast, adjust=False).mean()
        df["ema_" + str(ema_slow)] = df["close"].ewm(span=ema_slow, adjust=False).mean()
        df["daily_return"] = df["close"].pct_change()
        df["vol_" + str(vol_window)] = df["daily_return"].rolling(vol_window).std()
        loop_start = max(50, ema_slow)
        if len(df) < loop_start:
            return {"error": "insufficient_data", "win_rate": 0, "max_drawdown": 0}
    elif strategy_name == "EMA_trend_v3":
        sc = get_strategy_config(strategy_name) or {}
        ema_fast = sc.get("ema_fast", 80)
        ema_slow = sc.get("ema_slow", 200)
        vol_window = sc.get("vol_window", 20)
        adx_period = sc.get("adx_period", 14)
        macd_fast = sc.get("macd_fast", 12)
        macd_slow = sc.get("macd_slow", 26)
        macd_signal = sc.get("macd_signal", 9)
        df["ema_" + str(ema_fast)] = df["close"].ewm(span=ema_fast, adjust=False).mean()
        df["ema_" + str(ema_slow)] = df["close"].ewm(span=ema_slow, adjust=False).mean()
        df["daily_return"] = df["close"].pct_change()
        df["vol_" + str(vol_window)] = df["daily_return"].rolling(vol_window).std()
        df["sma_200"] = calculate_ma(df["close"], 200)
        df["adx_" + str(adx_period)] = calculate_adx(
            df["high"], df["low"], df["close"], period=adx_period
        )
        macd_line, _, _ = calculate_macd(
            df["close"], fast=macd_fast, slow=macd_slow, signal=macd_signal
        )
        df["macd_line"] = macd_line
        loop_start = 200
        if len(df) < loop_start:
            return {"error": "insufficient_data", "win_rate": 0, "max_drawdown": 0}
    elif strategy_name == "NDX_MA50_Volume_RSI":
        df["ma50"] = calculate_ma(df["close"], 50)
        df["ma20"] = calculate_ma20(df["close"])
        df["rsi_14"] = calculate_rsi_handwrite(df["close"], 14)
        df["volume_ratio"] = calculate_volume_ratio(df["volume"], 20)
        loop_start = 60
        if len(df) < loop_start:
            return {"error": "insufficient_data", "win_rate": 0, "max_drawdown": 0}
    else:
        df["ma50"] = calculate_ma(df["close"], 50)
        df["ma5"] = calculate_ma5(df["close"])
        df["ma20"] = calculate_ma20(df["close"])
        df["rsi_9"] = calculate_rsi_handwrite(df["close"], 9)
        df["rsi_24"] = calculate_rsi_handwrite(df["close"], 24)
        df["volume_ratio"] = calculate_volume_ratio(df["volume"], 20)

    position = 0.0
    entries: list = []  # (date, price, side, size, stop_loss, take_profit) 开仓时保存 sl/tp
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    wins = 0
    losses = 0
    closed_pnls: List[float] = []  # v2: 每笔平仓 PnL，用于 profit_factor
    bar_returns: List[float] = []  # v2: 每 Bar 权益变化率，用于夏普
    circuit_breaker_cooldown = 0
    prev_equity = equity
    series_rows: List[Dict[str, Any]] = []  # v4: 按日序列，return_series=True 时填充
    close_start = float(df["close"].iloc[loop_start]) if loop_start < len(df) else 1.0

    if next_day_execution:
        # T 日信号 → T+1 日执行：当日收益由「上一日信号」决定的仓位产生，无 Bar 内 SL/TP
        prev_pos_new = 0.0
        entry_price = 0.0
        for i in range(loop_start, len(df)):
            window = df.iloc[: i + 1]
            row = df.iloc[i]
            price = float(row["close"])
            date = df.index[i]
            position_held = prev_pos_new  # 本 Bar 持仓 = 上一 Bar 的信号
            current_position_info = None
            if position_held != 0:
                direction = "long" if position_held > 0 else "short"
                current_position_info = {"direction": direction, "entry_reason": ""}
            sig = strategy.generate_signal(window, current_position_info=current_position_info)
            pos_new = float(sig.get("position", 0.0) or 0.0)

            # 本 Bar 收益：由 position_held 产生（次日执行，故用昨日信号）
            if i > loop_start and position_held != 0:
                prev_close = float(df["close"].iloc[i - 1])
                daily_ret = (price - prev_close) / prev_close
                if position_held < 0:
                    daily_ret = -daily_ret
                ret = daily_ret * abs(position_held)
                equity *= 1.0 + ret
            # 仓位变化：收手续费；若平仓则记一笔交易
            if pos_new != position_held:
                equity *= 1.0 - 2.0 * commission
                if position_held != 0:
                    if position_held > 0:
                        trade_ret = (price - entry_price) / entry_price
                    else:
                        trade_ret = (entry_price - price) / entry_price
                    closed_pnls.append(trade_ret)
                    if trade_ret > 0:
                        wins += 1
                    else:
                        losses += 1
                if pos_new != 0:
                    entry_price = price
            prev_pos_new = pos_new

            if equity > peak:
                peak = equity
            max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0)
            if position_held == 0 and accrue_risk_free_when_flat:
                equity *= 1.0 + rfr_daily
                if equity > peak:
                    peak = equity
                max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0)
            if prev_equity > 0:
                bar_returns.append((equity - prev_equity) / prev_equity)
            else:
                bar_returns.append(0.0)
            prev_equity = equity
            if return_series:
                bench_cum = price / close_start
                series_rows.append({
                    "date": date,
                    "equity": equity,
                    "strategy_cum_return": equity,
                    "benchmark_cum_return": bench_cum,
                    "position": position_held,
                })
    else:
        for i in range(loop_start, len(df)):
            window = df.iloc[: i + 1]
            row = df.iloc[i]
            # TASK-11：传入当前持仓信息以支持平仓信号
            current_position_info = None
            if position != 0 and entries:
                direction = "long" if position > 0 else "short"
                entry_reason = entries[-1][6] if len(entries[-1]) > 6 else ""
                current_position_info = {"direction": direction, "entry_reason": entry_reason}
            sig = strategy.generate_signal(window, current_position_info=current_position_info)
            risk = strategy.calculate_risk(sig, window)
            price = row["close"]
            high = row["high"]
            low = row["low"]
            ma50 = row["ma50"] if "ma50" in df.columns else None
            date = df.index[i]
            pos_new = sig.get("position", 0.0)

            dd = (peak - equity) / peak if peak > 0 else 0.0
            allow_new_position = True
            if cb_enabled:
                if dd >= cb_threshold and position != 0:
                    # 熔断：平仓（或降仓至 position_after，此处简化为平仓）
                    entry_price = entries[-1][1] if entries else price
                    side = 1 if position > 0 else -1
                    ret = (price - entry_price) / entry_price * side - commission * 2
                    closed_pnls.append(ret)
                    if ret > 0:
                        wins += 1
                    else:
                        losses += 1
                    equity *= 1 + ret
                    if equity > peak:
                        peak = equity
                    max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0)
                    position = 0.0
                    entries.clear()
                    circuit_breaker_cooldown = cb_cooldown_bars
                if circuit_breaker_cooldown > 0:
                    allow_new_position = False
                    circuit_breaker_cooldown -= 1

            # ----- 若当前有仓位：先检查止损/止盈（v2，使用开仓时保存的 sl/tp） -----
            closed_by_sl_tp = False
            if position != 0 and use_sl_tp and entries:
                entry_price = entries[-1][1]
                # 开仓时已存 (date, price, side, size, sl, tp)
                sl = entries[-1][4] if len(entries[-1]) > 5 else risk.get("stop_loss", price)
                tp = entries[-1][5] if len(entries[-1]) > 5 else risk.get("take_profit", price)
                side = 1 if position > 0 else -1
                exit_price = None
                if position > 0:  # 多头
                    if low <= sl:
                        exit_price = sl
                    elif high >= tp:
                        exit_price = tp
                else:  # 空头
                    if high >= sl:
                        exit_price = sl
                    elif low <= tp:
                        exit_price = tp
                if exit_price is not None:
                    ret = (exit_price - entry_price) / entry_price * side - commission * 2
                    closed_pnls.append(ret)
                    if ret > 0:
                        wins += 1
                    else:
                        losses += 1
                    equity *= 1 + ret
                    if equity > peak:
                        peak = equity
                    max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0)
                    position = 0.0
                    entries.clear()
                    closed_by_sl_tp = True

            # ----- 若未因止损止盈平仓：可选趋势破位（v2，仅当有 ma50 时） -----
            if not closed_by_sl_tp and position != 0 and use_ma50_exit and entries and ma50 is not None:
                entry_price = entries[-1][1]
                side = 1 if position > 0 else -1
                exit_ma = False
                if position > 0 and price < ma50:
                    exit_ma = True
                elif position < 0 and price > ma50:
                    exit_ma = True
                if exit_ma:
                    ret = (price - entry_price) / entry_price * side - commission * 2
                    closed_pnls.append(ret)
                    if ret > 0:
                        wins += 1
                    else:
                        losses += 1
                    equity *= 1 + ret
                    if equity > peak:
                        peak = equity
                    max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0)
                    position = 0.0
                    entries.clear()
                    closed_by_sl_tp = True

            # ----- 信号驱动开平仓（熔断期间禁止新开仓） -----
            if closed_by_sl_tp:
                # 本 Bar 已平仓，不再按信号开反向仓（下一 Bar 再开）
                pass
            elif pos_new != 0 and position == 0 and allow_new_position:
                position = pos_new
                sl = risk.get("stop_loss", price)
                tp = risk.get("take_profit", price)
                entries.append((date, price, "buy" if pos_new > 0 else "sell", abs(pos_new), sl, tp, sig.get("reason", "")))
            elif (pos_new == 0 or (pos_new > 0 != position > 0)) and position != 0:
                entry_price = entries[-1][1] if entries else price
                side = 1 if position > 0 else -1
                ret = (price - entry_price) / entry_price * side - commission * 2
                closed_pnls.append(ret)
                if ret > 0:
                    wins += 1
                else:
                    losses += 1
                equity *= 1 + ret
                if equity > peak:
                    peak = equity
                max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0)
                position = pos_new
                if position != 0:
                    sl = risk.get("stop_loss", price)
                    tp = risk.get("take_profit", price)
                    entries.append((date, price, "buy" if position > 0 else "sell", abs(position), sl, tp, sig.get("reason", "")))
                else:
                    entries.clear()

            # 空仓时按无风险利率对权益计息（日复利），更贴近实际资金机会成本
            if position == 0 and accrue_risk_free_when_flat:
                equity *= 1.0 + rfr_daily
                if equity > peak:
                    peak = equity
                max_dd = max(max_dd, (peak - equity) / peak if peak > 0 else 0)

            # v2: 本 Bar 权益变化率，用于夏普
            if prev_equity > 0:
                bar_returns.append((equity - prev_equity) / prev_equity)
            else:
                bar_returns.append(0.0)
            prev_equity = equity

            # v4: 按日序列
            if return_series:
                bench_cum = float(df["close"].iloc[i]) / close_start
                series_rows.append({
                    "date": date,
                    "equity": equity,
                    "strategy_cum_return": equity,
                    "benchmark_cum_return": bench_cum,
                    "position": position,
                })

    total_trades = wins + losses
    win_rate = wins / total_trades if total_trades else 0
    total_return = equity - 1.0

    # v2: 标准绩效指标
    gross_profit = sum(p for p in closed_pnls if p > 0)
    gross_loss = abs(sum(p for p in closed_pnls if p < 0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 99.0

    years = max((pd.to_datetime(end_date) - pd.to_datetime(start_date)).days / 365.0, 0.1)
    if bar_returns:
        returns_arr = pd.Series(bar_returns)
        ann_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else total_return
        ann_vol = float(returns_arr.std() * math.sqrt(252)) if len(returns_arr) > 1 else 1e-8
        sharpe = (ann_return - risk_free_rate) / (ann_vol + 1e-8) if ann_vol else 0.0
    else:
        sharpe = 0.0

    # 基准（买入持有）绩效：与策略同区间 loop_start ~ 结束
    bench_cum_final = float(df["close"].iloc[-1]) / close_start
    benchmark_total_return = bench_cum_final - 1.0
    bench_cum_series = df["close"].iloc[loop_start:].astype(float) / close_start
    bench_rolling_max = bench_cum_series.cummax()
    bench_dd = (bench_cum_series - bench_rolling_max) / bench_rolling_max.replace(0, 1e-10)
    benchmark_max_drawdown = float(abs(bench_dd.min()))  # 与策略一致，存为正值
    bench_daily = df["close"].iloc[loop_start:].pct_change().dropna()
    benchmark_ann_return = (1.0 + benchmark_total_return) ** (1.0 / years) - 1.0 if years > 0 else benchmark_total_return
    benchmark_ann_vol = float(bench_daily.std() * math.sqrt(252)) if len(bench_daily) > 1 else 1e-8
    benchmark_sharpe = (benchmark_ann_return - risk_free_rate) / (benchmark_ann_vol + 1e-8) if benchmark_ann_vol else 0.0

    result = {
        "strategy": {
            "total_return": round(total_return, 4),
            "max_drawdown": round(max_dd, 4),
            "sharpe_ratio": round(sharpe, 4),
            "win_rate": round(win_rate, 4),
            "total_trades": total_trades,
            "profit_factor": round(profit_factor, 4),
        },
        "benchmark": {
            "total_return": round(benchmark_total_return, 4),
            "max_drawdown": round(benchmark_max_drawdown, 4),
            "sharpe_ratio": round(benchmark_sharpe, 4),
        },
        # 兼容旧代码：顶层保留 strategy 的 key，便于 result["total_return"] 等仍可用
        "total_return": round(total_return, 4),
        "max_drawdown": round(max_dd, 4),
        "sharpe_ratio": round(sharpe, 4),
        "win_rate": round(win_rate, 4),
        "total_trades": total_trades,
        "profit_factor": round(profit_factor, 4),
    }
    if return_series and series_rows:
        series_df = pd.DataFrame(series_rows).set_index("date")
        return (result, series_df)
    return result
