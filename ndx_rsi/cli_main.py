"""
CLI 入口：fetch_data、run_backtest、run_signal、verify_indicators。
"""
import argparse
import sys
from datetime import date
from pathlib import Path

# 确保包可被导入（当以 python -m ndx_rsi.cli_main 或脚本方式运行时）
if __name__ == "__main__" and str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def cmd_fetch_data(args: argparse.Namespace) -> int:
    from ndx_rsi.config_loader import get_datasource_config
    from ndx_rsi.data import YFinanceDataSource, preprocess_ohlcv

    config = get_datasource_config(args.symbol) or {"code": args.symbol}
    ds = YFinanceDataSource(args.symbol, config)
    df = ds.get_historical_data(args.start, args.end, args.frequency or "1d")
    df, ok = preprocess_ohlcv(df)
    print(f"Fetched {len(df)} rows. OK={ok}")
    if args.output:
        df.to_csv(args.output)
        print(f"Saved to {args.output}")
    return 0


def cmd_run_backtest(args: argparse.Namespace) -> int:
    from ndx_rsi.backtest import run_backtest
    from ndx_rsi.plot import plot_cumulative_returns

    need_series = getattr(args, "plot", False) or getattr(args, "save_plot", None)
    start = args.start or "2003-01-01"
    end = args.end or date.today().isoformat()
    if need_series:
        result, series_df = run_backtest(
            strategy_name=args.strategy or "NDX_short_term",
            symbol=args.symbol or "QQQ",
            start_date=start,
            end_date=end,
            return_series=True,
        )
    else:
        result = run_backtest(
            strategy_name=args.strategy or "NDX_short_term",
            symbol=args.symbol or "QQQ",
            start_date=start,
            end_date=end,
        )
    if "error" in result:
        print("Error:", result["error"])
        return 1
    # 策略 vs 基准对比输出
    if "strategy" in result and "benchmark" in result:
        s, b = result["strategy"], result["benchmark"]
        print("=" * 56)
        print("  Backtest 策略 vs 基准（买入持有）")
        print("=" * 56)
        print(f"  {'指标':<18} {'策略':>12} {'基准':>12} {'差异':>10}")
        print("-" * 56)
        sr, br = s.get("total_return", 0), b.get("total_return", 0)
        print(f"  {'累计收益率':<18} {sr:>11.2%} {br:>11.2%} {(sr - br):>+9.2%}")
        print(f"  {'最大回撤':<18} {s.get('max_drawdown', 0):>11.2%} {b.get('max_drawdown', 0):>11.2%} {(s.get('max_drawdown', 0) - b.get('max_drawdown', 0)):>+9.2%}")
        print(f"  {'夏普比率':<18} {s.get('sharpe_ratio', 0):>12.4} {b.get('sharpe_ratio', 0):>12.4} {(s.get('sharpe_ratio', 0) - b.get('sharpe_ratio', 0)):>+10.4}")
        print("-" * 56)
        print(f"  策略额外: 胜率 {s.get('win_rate', 0):.2%} | 交易次数 {s.get('total_trades', 0)} | 盈亏比 {s.get('profit_factor', 0):.2f}")
        print("=" * 56)
    else:
        print("Backtest result:", result)
    if need_series and not series_df.empty:
        title = f"{getattr(args, 'symbol', 'QQQ')} {getattr(args, 'strategy', 'NDX_short_term')} Cumulative Returns"
        save_path = getattr(args, "save_plot", None)
        show = getattr(args, "plot", False) and not save_path
        plot_cumulative_returns(series_df, title=title, save_path=save_path, show=show)
    return 0


def cmd_run_signal(args: argparse.Namespace) -> int:
    from ndx_rsi.config_loader import get_datasource_config, get_strategy_config
    from ndx_rsi.data import YFinanceDataSource, preprocess_ohlcv
    from ndx_rsi.report import format_signal_report
    from ndx_rsi.indicators import (
        calculate_rsi_handwrite,
        calculate_ma,
        calculate_volume_ratio,
    )
    from ndx_rsi.strategy.factory import create_strategy

    strategy_name = args.strategy or "NDX_short_term"
    config = get_datasource_config(args.symbol) or {"code": args.symbol}
    ds = YFinanceDataSource(args.symbol, config)
    # EMA 策略需要 200+ 根 K 线，用更长的历史拉取
    if strategy_name in ("EMA_cross_v1", "EMA_trend_v2"):
        import datetime
        end = datetime.date.today()
        start = end - datetime.timedelta(days=400)
        df = ds.get_historical_data(start.isoformat(), end.isoformat(), "1d")
    else:
        df = ds.get_realtime_data()
    df, _ = preprocess_ohlcv(df)

    if strategy_name == "EMA_cross_v1":
        sc = get_strategy_config(strategy_name) or {}
        short_ema = sc.get("short_ema", 50)
        long_ema = sc.get("long_ema", 200)
        min_bars = max(50, long_ema)
        if df.empty or len(df) < min_bars:
            print(f"Insufficient data for signal (need at least {min_bars} bars).")
            return 1
        df["ema_" + str(short_ema)] = df["close"].ewm(span=short_ema, adjust=False).mean()
        df["ema_" + str(long_ema)] = df["close"].ewm(span=long_ema, adjust=False).mean()
    elif strategy_name == "EMA_trend_v2":
        sc = get_strategy_config(strategy_name) or {}
        ema_fast = sc.get("ema_fast", 80)
        ema_slow = sc.get("ema_slow", 200)
        vol_window = sc.get("vol_window", 20)
        min_bars = max(50, ema_slow)
        if df.empty or len(df) < min_bars:
            print(f"Insufficient data for signal (need at least {min_bars} bars).")
            return 1
        df["ema_" + str(ema_fast)] = df["close"].ewm(span=ema_fast, adjust=False).mean()
        df["ema_" + str(ema_slow)] = df["close"].ewm(span=ema_slow, adjust=False).mean()
        df["daily_return"] = df["close"].pct_change()
        df["vol_" + str(vol_window)] = df["daily_return"].rolling(vol_window).std()
    else:
        if df.empty or len(df) < 50:
            print("Insufficient data for signal.")
            return 1
        df["ma50"] = calculate_ma(df["close"], 50)
        df["rsi_9"] = calculate_rsi_handwrite(df["close"], 9)
        df["rsi_24"] = calculate_rsi_handwrite(df["close"], 24)
        df["volume_ratio"] = calculate_volume_ratio(df["volume"], 20)

    strategy = create_strategy(strategy_name)
    sig = strategy.generate_signal(df)
    risk = strategy.calculate_risk(sig, df)
    report = format_signal_report(
        strategy_name, args.symbol, df, sig, risk,
        get_strategy_config(strategy_name),
    )
    print(report)
    return 0


def cmd_verify_indicators(args: argparse.Namespace) -> int:
    from ndx_rsi.config_loader import get_datasource_config
    from ndx_rsi.data import YFinanceDataSource, preprocess_ohlcv
    from ndx_rsi.indicators import verify_rsi

    config = get_datasource_config(args.symbol) or {"code": args.symbol}
    ds = YFinanceDataSource(args.symbol, config)
    df = ds.get_historical_data(args.start or "2024-01-01", args.end or "2025-01-01", "1d")
    df, _ = preprocess_ohlcv(df)
    if df.empty or len(df) < 30:
        print("Insufficient data for RSI verification.")
        return 1
    prices = df["close"]
    ok9 = verify_rsi(prices, 9, max_diff=0.1)
    ok24 = verify_rsi(prices, 24, max_diff=0.1)
    print(f"RSI(9)  handwrite vs TA-Lib: {'PASS' if ok9 else 'FAIL'}")
    print(f"RSI(24) handwrite vs TA-Lib: {'PASS' if ok24 else 'FAIL'}")
    return 0 if (ok9 and ok24) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="NDX RSI Quant CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # fetch_data
    p1 = sub.add_parser("fetch_data", help="Fetch OHLCV and optionally save")
    p1.add_argument("--symbol", default="QQQ", help="标的代码，如 QQQ、TQQQ、^NDX，用于拉取行情")
    p1.add_argument("--start", default="2024-01-01")
    p1.add_argument("--end", default="2025-01-01")
    p1.add_argument("--frequency", default="1d")
    p1.add_argument("--output", "-o", default=None)
    p1.set_defaults(func=cmd_fetch_data)

    # run_backtest
    p2 = sub.add_parser("run_backtest", help="Run backtest and print metrics")
    p2.add_argument("--strategy", default="NDX_short_term", help="策略名：NDX_short_term, EMA_cross_v1, EMA_trend_v2")
    p2.add_argument("--symbol", default="QQQ", help="回测标的，如 QQQ、TQQQ")
    p2.add_argument("--start", default="2003-01-01", help="回测起始日期，与 nasdaq_v1 一致")
    p2.add_argument("--end", default=None, help="回测结束日期，默认今日")
    p2.add_argument("--plot", action="store_true", help="回测完成后弹窗显示累计收益图")
    p2.add_argument("--save-plot", metavar="PATH", default=None, help="回测完成后保存累计收益图到指定路径")
    p2.set_defaults(func=cmd_run_backtest)

    # run_signal
    p3 = sub.add_parser("run_signal", help="Generate signal for latest data")
    p3.add_argument("--strategy", default="NDX_short_term")
    p3.add_argument("--symbol", default="QQQ", help="信号标的，如 QQQ、TQQQ")
    p3.set_defaults(func=cmd_run_signal)

    # verify_indicators
    p4 = sub.add_parser("verify_indicators", help="Verify RSI handwrite vs TA-Lib")
    p4.add_argument("--symbol", default="QQQ", help="验证 RSI 所用的行情标的")
    p4.add_argument("--start", default="2024-01-01")
    p4.add_argument("--end", default="2025-01-01")
    p4.set_defaults(func=cmd_verify_indicators)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
