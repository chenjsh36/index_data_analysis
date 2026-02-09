"""
CLI 入口：fetch_data、run_backtest、run_signal、verify_indicators。
"""
import argparse
import sys
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

    result = run_backtest(
        strategy_name=args.strategy or "NDX_short_term",
        symbol=args.symbol or "QQQ",
        start_date=args.start or "2018-01-01",
        end_date=args.end or "2025-01-01",
    )
    if "error" in result:
        print("Error:", result["error"])
        return 1
    print("Backtest result:", result)
    return 0


def cmd_run_signal(args: argparse.Namespace) -> int:
    from ndx_rsi.config_loader import get_datasource_config
    from ndx_rsi.data import YFinanceDataSource, preprocess_ohlcv
    from ndx_rsi.indicators import (
        calculate_rsi_handwrite,
        calculate_ma,
        calculate_volume_ratio,
    )
    from ndx_rsi.strategy.factory import create_strategy

    config = get_datasource_config(args.symbol) or {"code": args.symbol}
    ds = YFinanceDataSource(args.symbol, config)
    df = ds.get_realtime_data()
    df, _ = preprocess_ohlcv(df)
    if df.empty or len(df) < 50:
        print("Insufficient data for signal.")
        return 1
    df["ma50"] = calculate_ma(df["close"], 50)
    df["rsi_9"] = calculate_rsi_handwrite(df["close"], 9)
    df["rsi_24"] = calculate_rsi_handwrite(df["close"], 24)
    df["volume_ratio"] = calculate_volume_ratio(df["volume"], 20)
    strategy = create_strategy(args.strategy or "NDX_short_term")
    sig = strategy.generate_signal(df)
    risk = strategy.calculate_risk(sig, df)
    print("Signal:", sig)
    print("Risk:", risk)
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
    p2.add_argument("--strategy", default="NDX_short_term")
    p2.add_argument("--symbol", default="QQQ", help="回测标的，如 QQQ、TQQQ")
    p2.add_argument("--start", default="2018-01-01")
    p2.add_argument("--end", default="2025-01-01")
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
