#!/usr/bin/env python3
"""
v6: 跑信号并将报告推送到邮件、钉钉（CUSTOM_WEBHOOK_URLS）。
从项目根运行: PYTHONPATH=. python scripts/run_signal_and_notify.py
环境变量: EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVERS; CUSTOM_WEBHOOK_URLS（逗号分隔）; 可选 SYMBOL, STRATEGY.
"""
import os
import sys
from pathlib import Path

# 保证项目根在 path 中，便于 import ndx_rsi
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _get_report(symbol: str, strategy_name: str) -> str:
    """执行 run_signal 逻辑并返回报告文本（不打印）。"""
    from ndx_rsi.config_loader import get_datasource_config, get_strategy_config
    from ndx_rsi.data import YFinanceDataSource, preprocess_ohlcv
    from ndx_rsi.report import format_signal_report
    from ndx_rsi.indicators import (
        calculate_ma,
        calculate_rsi_handwrite,
        calculate_volume_ratio,
        calculate_adx,
        calculate_macd,
    )
    from ndx_rsi.strategy.factory import create_strategy

    config = get_datasource_config(symbol) or {"code": symbol}
    ds = YFinanceDataSource(symbol, config)
    if strategy_name in ("EMA_cross_v1", "EMA_trend_v2", "EMA_trend_v3"):
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
            return f"【无数据】需要至少 {min_bars} 根 K 线。"
        df["ema_" + str(short_ema)] = df["close"].ewm(span=short_ema, adjust=False).mean()
        df["ema_" + str(long_ema)] = df["close"].ewm(span=long_ema, adjust=False).mean()
    elif strategy_name == "EMA_trend_v2":
        sc = get_strategy_config(strategy_name) or {}
        ema_fast = sc.get("ema_fast", 80)
        ema_slow = sc.get("ema_slow", 200)
        vol_window = sc.get("vol_window", 20)
        min_bars = max(50, ema_slow)
        if df.empty or len(df) < min_bars:
            return f"【无数据】需要至少 {min_bars} 根 K 线。"
        df["ema_" + str(ema_fast)] = df["close"].ewm(span=ema_fast, adjust=False).mean()
        df["ema_" + str(ema_slow)] = df["close"].ewm(span=ema_slow, adjust=False).mean()
        df["daily_return"] = df["close"].pct_change()
        df["vol_" + str(vol_window)] = df["daily_return"].rolling(vol_window).std()
    elif strategy_name == "EMA_trend_v3":
        sc = get_strategy_config(strategy_name) or {}
        ema_fast = sc.get("ema_fast", 80)
        ema_slow = sc.get("ema_slow", 200)
        vol_window = sc.get("vol_window", 20)
        adx_period = sc.get("adx_period", 14)
        macd_fast = sc.get("macd_fast", 12)
        macd_slow = sc.get("macd_slow", 26)
        macd_signal = sc.get("macd_signal", 9)
        min_bars = 200
        if df.empty or len(df) < min_bars:
            return f"【无数据】需要至少 {min_bars} 根 K 线。"
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
    else:
        if df.empty or len(df) < 50:
            return "【无数据】K 线不足。"
        df["ma50"] = calculate_ma(df["close"], 50)
        df["rsi_9"] = calculate_rsi_handwrite(df["close"], 9)
        df["rsi_24"] = calculate_rsi_handwrite(df["close"], 24)
        df["volume_ratio"] = calculate_volume_ratio(df["volume"], 20)

    strategy = create_strategy(strategy_name)
    sig = strategy.generate_signal(df)
    risk = strategy.calculate_risk(sig, df)
    return format_signal_report(
        strategy_name, symbol, df, sig, risk,
        get_strategy_config(strategy_name),
    )


def _send_email(report: str, symbol: str = "QQQ") -> bool:
    """若配置了 EMAIL_SENDER/EMAIL_PASSWORD，则用 SMTP 发送纯文本邮件。"""
    sender = os.environ.get("EMAIL_SENDER", "").strip()
    password = os.environ.get("EMAIL_PASSWORD", "").strip()
    receivers_str = os.environ.get("EMAIL_RECEIVERS", "").strip()
    if not sender or not password:
        return False
    receivers = [r.strip() for r in receivers_str.split(",") if r.strip()] if receivers_str else [sender]

    # 常见 SMTP 端口（与 daily_stock_analysis 对齐）
    domain = sender.split("@")[-1].lower() if "@" in sender else ""
    smtp_configs = {
        "qq.com": ("smtp.qq.com", 465, True),
        "foxmail.com": ("smtp.qq.com", 465, True),
        "163.com": ("smtp.163.com", 465, True),
        "126.com": ("smtp.126.com", 465, True),
        "gmail.com": ("smtp.gmail.com", 587, False),
        "outlook.com": ("smtp-mail.outlook.com", 587, False),
        "aliyun.com": ("smtp.aliyun.com", 465, True),
    }
    server, port, use_ssl = smtp_configs.get(domain, ("smtp." + domain if domain else "", 465, True))

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.header import Header

        msg = MIMEText(report, "plain", "utf-8")
        msg["Subject"] = Header(f"{symbol} 信号 - {str(__import__('datetime').date.today())}", "utf-8")
        msg["From"] = sender
        msg["To"] = ",".join(receivers)

        if use_ssl:
            with smtplib.SMTP_SSL(server, port) as smtp:
                smtp.login(sender, password)
                smtp.sendmail(sender, receivers, msg.as_string())
        else:
            with smtplib.SMTP(server, port) as smtp:
                smtp.starttls()
                smtp.login(sender, password)
                smtp.sendmail(sender, receivers, msg.as_string())
        return True
    except Exception as e:
        print(f"Email send failed: {e}", file=sys.stderr)
        return False


def _send_webhooks(report: str) -> int:
    """若配置了 CUSTOM_WEBHOOK_URLS（逗号分隔），则对每个 URL POST 钉钉格式 JSON。返回成功个数。"""
    urls_str = os.environ.get("CUSTOM_WEBHOOK_URLS", "").strip()
    if not urls_str:
        return 0
    import requests

    urls = [u.strip() for u in urls_str.split(",") if u.strip()]
    payload = {"msgtype": "text", "text": {"content": report}}
    ok = 0
    for url in urls:
        try:
            r = requests.post(url, json=payload, timeout=10)
            if r.status_code == 200:
                ok += 1
            else:
                print(f"Webhook {url} -> {r.status_code}", file=sys.stderr)
        except Exception as e:
            print(f"Webhook {url} error: {e}", file=sys.stderr)
    return ok


if __name__ == "__main__":
    symbol = os.environ.get("SYMBOL", "QQQ").strip()
    strategy_name = os.environ.get("STRATEGY", "EMA_trend_v2").strip()

    report = _get_report(symbol, strategy_name)
    print(report)

    sent_email = _send_email(report, symbol=symbol)
    sent_webhooks = _send_webhooks(report)
    if sent_email or sent_webhooks:
        print(f"Notify: email={sent_email}, webhooks={sent_webhooks}", file=sys.stderr)
    else:
        print("No EMAIL_* or CUSTOM_WEBHOOK_URLS set, skip notify.", file=sys.stderr)
