"""
run_signal 可读报告与推导逻辑展示。
按策略分支拼装：日期、收盘价、指标、推导逻辑、操作建议、止损止盈。
"""
from typing import Any, Dict, Optional

import pandas as pd


def _fmt_date(idx) -> str:
    """将 DataFrame 索引最后一格格式化为 YYYY-MM-DD。"""
    try:
        ts = idx
        if hasattr(ts, "strftime"):
            return ts.strftime("%Y-%m-%d")
        return str(ts)[:10]
    except Exception:
        return str(idx)[:10]


def _get(row: pd.Series, key: str, default: str = "N/A"):
    if key not in row.index:
        return default
    v = row[key]
    if pd.isna(v):
        return default
    if isinstance(v, float):
        return f"{v:.4g}" if abs(v) < 1e-4 or abs(v) >= 1e4 else f"{v:.2f}"
    return str(v)


def _action_from_position(sig: Dict[str, Any]) -> str:
    pos = sig.get("position", 0)
    if pos is None:
        return "观望"
    p = float(pos)
    if p >= 0.99:
        return "满仓持有"
    if p > 0:
        return f"部分持仓({p:.0%})"
    if p <= -0.99:
        return "空仓/做空"
    if p < 0:
        return f"轻空仓({p:.0%})"
    return "空仓观望"


def _build_common_tail(risk: Dict[str, Any], lines: list) -> None:
    sl = risk.get("stop_loss")
    tp = risk.get("take_profit")
    if sl is not None and sl != 0:
        lines.append(f"  止损: {sl:.2f}")
    if tp is not None and tp != 0:
        lines.append(f"  止盈: {tp:.2f}")


def _report_ema_cross_v1(
    symbol: str, row: pd.Series, date_str: str, sig: Dict[str, Any], risk: Dict[str, Any], config: Optional[Dict]
) -> str:
    short_ema = (config or {}).get("short_ema", 50)
    long_ema = (config or {}).get("long_ema", 200)
    ema_s = f"ema_{short_ema}"
    ema_l = f"ema_{long_ema}"
    v1 = _get(row, ema_s)
    v2 = _get(row, ema_l)
    close = _get(row, "close")

    reason = (sig.get("reason") or "").strip()
    position = float(sig.get("position", 0) or 0)

    if reason == "golden_cross":
        derivation = f"EMA{short_ema}({v1}) 上穿 EMA{long_ema}({v2}) → 黄金交叉 → 建议买入/持有"
    elif reason == "death_cross":
        derivation = f"EMA{short_ema}({v1}) 下穿 EMA{long_ema}({v2}) → 死亡交叉 → 建议卖出/空仓"
    elif reason.startswith("monthly_rebalance"):
        derivation = f"月末调仓：EMA{short_ema} vs EMA{long_ema} → {'做多' if position else '空仓'}"
    elif reason == "hold_until_month_end":
        derivation = "未到月末调仓日 → 维持当前仓位"
    elif reason == "hold":
        try:
            ema_short_val = row[ema_s] if ema_s in row.index else None
            ema_long_val = row[ema_l] if ema_l in row.index else None
            if ema_short_val is not None and ema_long_val is not None and pd.notna(ema_short_val) and pd.notna(ema_long_val):
                up = float(ema_short_val) > float(ema_long_val)
                if position >= 0.5:
                    derivation = f"EMA{short_ema}({v1}) {'>' if up else '<'} EMA{long_ema}({v2})，{'趋势向上' if up else '趋势向下'}，未发生交叉 → 维持持有"
                else:
                    derivation = f"EMA{short_ema}({v1}) {'>' if up else '<'} EMA{long_ema}({v2})，{'趋势向上' if up else '趋势向下'}，未发生交叉 → 维持空仓"
            else:
                derivation = "未发生交叉 → 维持当前仓位"
        except Exception:
            derivation = "未发生交叉 → 维持当前仓位"
    else:
        derivation = reason or "—"

    action = _action_from_position(sig)
    lines = [
        "=" * 55,
        f"【{symbol} EMA均线交叉(v1) 信号 - {date_str}】",
        f"  收盘价: {close}",
        f"  EMA{short_ema}: {v1}",
        f"  EMA{long_ema}: {v2}",
        f"  推导逻辑: {derivation}",
        f"  操作建议: {action}",
    ]
    _build_common_tail(risk, lines)
    lines.append("=" * 55)
    return "\n".join(lines)


def _report_ema_trend_v2(
    symbol: str, row: pd.Series, date_str: str, sig: Dict[str, Any], risk: Dict[str, Any], config: Optional[Dict]
) -> str:
    fast = (config or {}).get("ema_fast", 80)
    slow = (config or {}).get("ema_slow", 200)
    vol_window = (config or {}).get("vol_window", 20)
    vol_threshold = (config or {}).get("vol_threshold", 0.02)
    ema_f = f"ema_{fast}"
    ema_s = f"ema_{slow}"
    vol_col = f"vol_{vol_window}"

    v_f = _get(row, ema_f)
    v_s = _get(row, ema_s)
    vol_val = _get(row, vol_col)
    close = _get(row, "close")

    reason = (sig.get("reason") or "").strip()
    position = float(sig.get("position", 0) or 0)
    uptrend = reason == "uptrend_low_vol" and position >= 0.5
    if uptrend:
        derivation = f"EMA{fast}({v_f}) > EMA{slow}({v_s}) → 上升趋势；{vol_col}({vol_val}) < {vol_threshold} → 低波动；上升+低波动 → 满仓持有"
    else:
        derivation = f"EMA{fast}({v_f}) vs EMA{slow}({v_s})；{vol_col}({vol_val}) 阈值{vol_threshold}；未满足「上升+低波动」→ 空仓/减仓"

    action = _action_from_position(sig)
    lines = [
        "=" * 55,
        f"【{symbol} EMA趋势增强(v2) 信号 - {date_str}】",
        f"  收盘价: {close}",
        f"  EMA{fast}: {v_f}",
        f"  EMA{slow}: {v_s}",
        f"  20日波动率: {vol_val}  (阈值: {vol_threshold})",
        f"  推导逻辑: {derivation}",
        f"  操作建议: {action}",
    ]
    _build_common_tail(risk, lines)
    lines.append("=" * 55)
    return "\n".join(lines)


# NDX_short_term 常见 reason 到简短中文推导
_NDX_REASON_DERIVATION = {
    "no_signal": "RSI/均线/量能未触发买卖条件 → 观望",
    "golden_cross": "RSI 金叉 + 量能确认 → 建议加仓",
    "death_cross": "RSI 死叉 → 建议减仓/空仓",
    "close_overbought_exit": "超买区平仓退出 → 减仓",
    "close_oversell_exit": "超卖区平仓退出 → 观望或回补",
    "overbought": "RSI 超买 → 减仓/观望",
    "oversell": "RSI 超卖 → 考虑加仓",
    "bullish_divergence": "底背离 → 看多",
    "bearish_divergence": "顶背离 → 看空",
    "trend_pullback": "趋势回踩 + 量能 → 轻仓试多",
    "trend_bounce_sell": "反弹遇阻 → 减仓",
    "trend_bounce_sell_light": "反弹遇阻 → 轻减仓",
    "pullback_volume_reject": "回踩量能不足 → 观望",
    "overbought_with_volume_ignore": "超买但量能支撑 → 暂持",
    "extreme_market": "极端行情 → 观望",
    "insufficient_data": "数据不足 → 无法出信号",
}


def _report_ndx_short_term(
    symbol: str, row: pd.Series, date_str: str, sig: Dict[str, Any], risk: Dict[str, Any], config: Optional[Dict]
) -> str:
    close = _get(row, "close")
    ma50 = _get(row, "ma50")
    rsi_9 = _get(row, "rsi_9")
    rsi_24 = _get(row, "rsi_24")
    vol_ratio = _get(row, "volume_ratio")

    reason = (sig.get("reason") or "no_signal").strip()
    derivation = _NDX_REASON_DERIVATION.get(reason) or f"原因: {reason}"
    action = _action_from_position(sig)

    lines = [
        "=" * 55,
        f"【{symbol} NDX短线 信号 - {date_str}】",
        f"  收盘价: {close}",
        f"  MA50: {ma50}",
        f"  RSI(9): {rsi_9}",
        f"  RSI(24): {rsi_24}",
        f"  量能比: {vol_ratio}",
        f"  推导逻辑: {derivation}",
        f"  操作建议: {action}",
    ]
    _build_common_tail(risk, lines)
    lines.append("=" * 55)
    return "\n".join(lines)


def format_signal_report(
    strategy_name: str,
    symbol: str,
    df: pd.DataFrame,
    sig: Dict[str, Any],
    risk: Dict[str, Any],
    strategy_config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    生成 run_signal 的可读报告（含推导逻辑）。
    df 至少含最后一根 K 线及该策略已预计算的指标列。
    """
    if df.empty:
        return "【无数据】无法生成报告。"
    row = df.iloc[-1]
    date_str = _fmt_date(df.index[-1])

    if strategy_name == "EMA_cross_v1":
        return _report_ema_cross_v1(symbol, row, date_str, sig, risk, strategy_config)
    if strategy_name == "EMA_trend_v2":
        return _report_ema_trend_v2(symbol, row, date_str, sig, risk, strategy_config)
    if strategy_name == "NDX_short_term":
        return _report_ndx_short_term(symbol, row, date_str, sig, risk, strategy_config)
    # 未知策略：通用简短报告
    action = _action_from_position(sig)
    lines = [
        "=" * 55,
        f"【{symbol} {strategy_name} 信号 - {date_str}】",
        f"  收盘价: {_get(row, 'close')}",
        f"  推导逻辑: {sig.get('reason', '—')}",
        f"  操作建议: {action}",
    ]
    _build_common_tail(risk, lines)
    lines.append("=" * 55)
    return "\n".join(lines)


def print_signal_report(
    strategy_name: str,
    symbol: str,
    df: pd.DataFrame,
    sig: Dict[str, Any],
    risk: Dict[str, Any],
    strategy_config: Optional[Dict[str, Any]] = None,
) -> None:
    """格式化并打印信号报告。"""
    print(format_signal_report(strategy_name, symbol, df, sig, risk, strategy_config))
