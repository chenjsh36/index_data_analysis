#!/usr/bin/env python3
"""
v6: 生成静态页用 JSON：timeseries.json（5 年 QQQ 走势）、signal.json（最近一次信号）。
从项目根运行: PYTHONPATH=. python scripts/generate_static_data.py [--out-dir web]
"""
import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_timeseries(symbol: str, years: int, out_dir: Path) -> None:
    """拉取近 years 年日线 close，写入 out_dir/timeseries.json。"""
    from ndx_rsi.config_loader import get_datasource_config
    from ndx_rsi.data import YFinanceDataSource, preprocess_ohlcv

    end = date.today()
    start = end - timedelta(days=years * 365)
    config = get_datasource_config(symbol) or {"code": symbol}
    ds = YFinanceDataSource(symbol, config)
    df = ds.get_historical_data(start.isoformat(), end.isoformat(), "1d")
    df, _ = preprocess_ohlcv(df)
    if df.empty:
        _write_json(out_dir / "timeseries.json", {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat(), "series": []})
        return
    series = []
    for idx in df.index:
        ts = idx
        d = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
        close = float(df.loc[idx, "close"])
        series.append([d, round(close, 4)])
    _write_json(
        out_dir / "timeseries.json",
        {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat(), "series": series},
    )


def generate_signal(symbol: str, strategy_name: str, out_dir: Path) -> None:
    """跑一次 signal，将结果写入 out_dir/signal.json。"""
    from ndx_rsi.config_loader import get_datasource_config, get_strategy_config
    from ndx_rsi.data import YFinanceDataSource, preprocess_ohlcv
    from ndx_rsi.report import signal_report_to_dict
    from ndx_rsi.strategy.factory import create_strategy

    config = get_datasource_config(symbol) or {"code": symbol}
    ds = YFinanceDataSource(symbol, config)
    end = date.today()
    start = end - timedelta(days=400)
    df = ds.get_historical_data(start.isoformat(), end.isoformat(), "1d")
    df, _ = preprocess_ohlcv(df)
    sc = get_strategy_config(strategy_name) or {}
    if strategy_name == "EMA_trend_v2":
        ema_fast = sc.get("ema_fast", 80)
        ema_slow = sc.get("ema_slow", 200)
        vol_window = sc.get("vol_window", 20)
        min_bars = max(50, ema_slow)
        if df.empty or len(df) < min_bars:
            _write_json(out_dir / "signal.json", {"error": "insufficient_data"})
            return
        df["ema_" + str(ema_fast)] = df["close"].ewm(span=ema_fast, adjust=False).mean()
        df["ema_" + str(ema_slow)] = df["close"].ewm(span=ema_slow, adjust=False).mean()
        df["daily_return"] = df["close"].pct_change()
        df["vol_" + str(vol_window)] = df["daily_return"].rolling(vol_window).std()
    else:
        if df.empty or len(df) < 50:
            _write_json(out_dir / "signal.json", {"error": "insufficient_data"})
            return
    strategy = create_strategy(strategy_name)
    sig = strategy.generate_signal(df)
    risk = strategy.calculate_risk(sig, df)
    payload = signal_report_to_dict(strategy_name, symbol, df, sig, risk, sc)
    if payload:
        _write_json(out_dir / "signal.json", payload)
    else:
        _write_json(out_dir / "signal.json", {"error": "unsupported_strategy", "strategy": strategy_name})


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate static JSON for web dashboard.")
    parser.add_argument("--symbol", default="QQQ", help="Symbol (default: QQQ)")
    parser.add_argument("--strategy", default="EMA_trend_v2", help="Strategy name")
    parser.add_argument("--years", type=int, default=5, help="Years of history for timeseries")
    parser.add_argument("--out-dir", type=Path, default=_ROOT / "web", help="Output directory")
    args = parser.parse_args()
    out_dir = args.out_dir.resolve()
    generate_timeseries(args.symbol, args.years, out_dir)
    generate_signal(args.symbol, args.strategy, out_dir)
    print(f"Generated {out_dir / 'timeseries.json'} and {out_dir / 'signal.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
