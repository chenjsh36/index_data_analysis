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


def _report_ema_trend_v3(
    symbol: str, row: pd.Series, date_str: str, sig: Dict[str, Any], risk: Dict[str, Any], config: Optional[Dict]
) -> str:
    """纳指机构级 v3：五条件、ADX、MACD、SMA200、推导逻辑、操作建议、止损止盈。"""
    cfg = config or {}
    fast = cfg.get("ema_fast", 80)
    slow = cfg.get("ema_slow", 200)
    adx_period = cfg.get("adx_period", 14)
    adx_threshold = cfg.get("adx_threshold", 25)
    close = _get(row, "close")
    ema_f = _get(row, f"ema_{fast}")
    ema_s = _get(row, f"ema_{slow}")
    sma200 = _get(row, "sma_200")
    adx_val = _get(row, f"adx_{adx_period}")
    macd_val = _get(row, "macd_line")
    vol_col = f"vol_{cfg.get('vol_window', 20)}"
    vol_val = _get(row, vol_col)
    vol_threshold = cfg.get("vol_threshold", 0.02)

    # 五条件满足情况
    try:
        c = float(row.get("close", 0))
        e80 = float(row.get(f"ema_{fast}", 0))
        e200 = float(row.get(f"ema_{slow}", 0))
        s200 = float(row.get("sma_200", 0))
        adx = float(row.get(f"adx_{adx_period}", 0))
        macd = float(row.get("macd_line", 0))
        c1 = "是" if e80 > e200 else "否"
        c2 = "是" if c > e80 else "否"
        c3 = "是" if adx > adx_threshold else "否"
        c4 = "是" if macd > 0 else "否"
        c5 = "是" if c > s200 else "否"
    except (TypeError, ValueError):
        c1 = c2 = c3 = c4 = c5 = "—"
    conditions_text = (
        f"  条件1 80EMA>200EMA: {c1}  |  条件2 收盘>80EMA: {c2}  |  "
        f"条件3 ADX>25: {c3}  |  条件4 MACD>0: {c4}  |  条件5 收盘>SMA200: {c5}"
    )

    reason = (sig.get("reason") or "").strip()
    _v3_derivation = {
        "all_conditions_met": "五条件均满足 → 强烈买入",
        "uptrend": "80EMA > 200EMA → 做多，其余条件供参考",
        "ema_not_uptrend": "80EMA ≤ 200EMA → 空仓",
        "vix_above_25": "VIX ≥ 25 → 空仓",
        "vol_above_threshold": "20日波动率超阈值 → 空仓",
        "missing_indicators": "指标缺失 → 无法出信号",
        "insufficient_data": "数据不足 → 无法出信号",
    }
    derivation = _v3_derivation.get(reason) or f"原因: {reason}"
    macd_side = "0轴上方" if (row.get("macd_line") or 0) > 0 else "0轴下方"

    # 五条件全满足时操作建议为「强烈买入」，否则按 position 映射
    if reason == "all_conditions_met":
        action = "强烈买入"
    else:
        action = _action_from_position(sig)
    lines = [
        "=" * 55,
        f"【{symbol} 纳指机构级(v3) 信号 - {date_str}】",
        f"  收盘价: {close}",
        f"  EMA{fast}: {ema_f}",
        f"  EMA{slow}: {ema_s}",
        f"  SMA200: {sma200}",
        f"  ADX({adx_period}): {adx_val}  (阈值: {adx_threshold})",
        f"  MACD线: {macd_val}  ({macd_side})",
        f"  {conditions_text}",
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


def _report_ndx_ma50_volume_rsi(
    symbol: str, row: pd.Series, date_str: str, sig: Dict[str, Any], risk: Dict[str, Any], config: Optional[Dict]
) -> str:
    """NDX_MA50_Volume_RSI：趋势类型、RSI(14)、量能比、操作建议、止损止盈。"""
    close = _get(row, "close")
    ma50 = _get(row, "ma50")
    trend_type = sig.get("trend_type") or "—"
    rsi_14 = _get(row, "rsi_14")
    vol_ratio = _get(row, "volume_ratio")
    reason = (sig.get("reason") or "").strip()
    operation = sig.get("operation") or sig.get("reason") or "观望"
    derivation = f"{trend_type} | RSI(14)={rsi_14} 量能比={vol_ratio} → {reason}"

    lines = [
        "=" * 55,
        f"【{symbol} NDX_MA50_Volume_RSI 信号 - {date_str}】",
        f"  收盘价: {close}",
        f"  SMA50: {ma50}",
        f"  趋势类型: {trend_type}",
        f"  RSI(14): {rsi_14}  量能比(20日均量): {vol_ratio}",
        f"  推导逻辑: {derivation}",
        f"  操作建议: {operation}",
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
    if strategy_name == "EMA_trend_v3":
        return _report_ema_trend_v3(symbol, row, date_str, sig, risk, strategy_config)
    if strategy_name == "NDX_short_term":
        return _report_ndx_short_term(symbol, row, date_str, sig, risk, strategy_config)
    if strategy_name == "NDX_MA50_Volume_RSI":
        return _report_ndx_ma50_volume_rsi(symbol, row, date_str, sig, risk, strategy_config)
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


def _float_or_none(row: pd.Series, key: str):
    """取 row 中 key 的浮点值，缺失或 NaN 返回 None。"""
    if key not in row.index:
        return None
    v = row[key]
    if pd.isna(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def signal_report_to_dict(
    strategy_name: str,
    symbol: str,
    df: pd.DataFrame,
    sig: Dict[str, Any],
    risk: Dict[str, Any],
    strategy_config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    生成供静态页/JSON 使用的信号字典（EMA_trend_v2）。
    与 format_signal_report 字段一致；未知策略返回 None。
    """
    if df.empty:
        return None
    row = df.iloc[-1]
    date_str = _fmt_date(df.index[-1])
    action = _action_from_position(sig)

    if strategy_name == "EMA_trend_v2":
        config = strategy_config or {}
        fast = config.get("ema_fast", 80)
        slow = config.get("ema_slow", 200)
        vol_window = config.get("vol_window", 20)
        vol_threshold = config.get("vol_threshold", 0.02)
        ema_f = f"ema_{fast}"
        ema_s = f"ema_{slow}"
        vol_col = f"vol_{vol_window}"
        v_f = _get(row, ema_f)
        v_s = _get(row, ema_s)
        vol_val = _get(row, vol_col)
        reason = (sig.get("reason") or "").strip()
        position = float(sig.get("position", 0) or 0)
        uptrend = reason == "uptrend_low_vol" and position >= 0.5
        if uptrend:
            derivation = f"EMA{fast}({v_f}) > EMA{slow}({v_s}) → 上升趋势；{vol_col}({vol_val}) < {vol_threshold} → 低波动；上升+低波动 → 满仓持有"
        else:
            derivation = f"EMA{fast}({v_f}) vs EMA{slow}({v_s})；{vol_col}({vol_val}) 阈值{vol_threshold}；未满足「上升+低波动」→ 空仓/减仓"
        return {
            "date": date_str,
            "symbol": symbol,
            "strategy": strategy_name,
            "close": _float_or_none(row, "close"),
            "ema_fast": _float_or_none(row, ema_f),
            "ema_slow": _float_or_none(row, ema_s),
            "vol_20": _float_or_none(row, vol_col),
            "derivation": derivation,
            "action": action,
            "stop_loss": risk.get("stop_loss"),
            "take_profit": risk.get("take_profit"),
        }
    if strategy_name == "EMA_trend_v3":
        cfg = strategy_config or {}
        fast = cfg.get("ema_fast", 80)
        slow = cfg.get("ema_slow", 200)
        adx_period = cfg.get("adx_period", 14)
        row = df.iloc[-1]
        try:
            c, e80, e200, s200 = float(row["close"]), float(row[f"ema_{fast}"]), float(row[f"ema_{slow}"]), float(row["sma_200"])
            adx_v, macd_v = float(row[f"adx_{adx_period}"]), float(row["macd_line"])
            conditions_met = [e80 > e200, c > e80, adx_v > (cfg.get("adx_threshold", 25)), macd_v > 0, c > s200]
        except (KeyError, TypeError, ValueError):
            conditions_met = []
        _v3_derivation = {
            "all_conditions_met": "五条件均满足 → 强烈买入",
            "uptrend": "80EMA > 200EMA → 做多，其余条件供参考",
            "ema_not_uptrend": "80EMA ≤ 200EMA → 空仓",
            "vix_above_25": "VIX ≥ 25 → 空仓",
            "vol_above_threshold": "20日波动率超阈值 → 空仓",
        }
        reason = (sig.get("reason") or "").strip()
        derivation = _v3_derivation.get(reason) or str(sig.get("reason", ""))
        v3_action = "强烈买入" if reason == "all_conditions_met" else action
        return {
            "date": date_str,
            "symbol": symbol,
            "strategy": strategy_name,
            "close": _float_or_none(row, "close"),
            "ema_fast": _float_or_none(row, f"ema_{fast}"),
            "ema_slow": _float_or_none(row, f"ema_{slow}"),
            "sma_200": _float_or_none(row, "sma_200"),
            "adx_14": _float_or_none(row, f"adx_{adx_period}"),
            "macd_line": _float_or_none(row, "macd_line"),
            "conditions_met": conditions_met,
            "derivation": derivation,
            "action": v3_action,
            "stop_loss": risk.get("stop_loss"),
            "take_profit": risk.get("take_profit"),
        }
    return None
