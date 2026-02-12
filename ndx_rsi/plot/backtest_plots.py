"""
回测可视化：累计收益对比、多策略对比。
基于 run_backtest(return_series=True) 返回的 series_df 绘图。
"""
from typing import Dict, Optional

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def plot_cumulative_returns(
    series_df: pd.DataFrame,
    *,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    show: bool = True,
) -> None:
    """
    绘制策略 vs 基准累计收益曲线。

    Args:
        series_df: 含 strategy_cum_return、benchmark_cum_return，index 为日期
        title: 图标题
        save_path: 保存路径（PNG）
        show: 是否 plt.show()
    """
    if series_df.empty or "strategy_cum_return" not in series_df.columns:
        return
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.plot(
        series_df.index,
        series_df["strategy_cum_return"],
        label="Strategy",
        linewidth=1.5,
        color="#2196F3",
    )
    if "benchmark_cum_return" in series_df.columns:
        ax.plot(
            series_df.index,
            series_df["benchmark_cum_return"],
            label="Buy & Hold (Benchmark)",
            linewidth=1.5,
            color="#888888",
        )
    ax.set_title(title or "Cumulative Returns Comparison", fontsize=14)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Cumulative Return (starting from 1)", fontsize=12)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Chart saved: {save_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)


def plot_compare_strategies(
    series_df_by_name: Dict[str, pd.DataFrame],
    *,
    title: Optional[str] = None,
    save_path: Optional[str] = None,
    show: bool = True,
) -> None:
    """
    多策略累计收益对比图。

    Args:
        series_df_by_name: 策略名 -> 含 strategy_cum_return 的 DataFrame
        title: 图标题
        save_path: 保存路径（PNG）
        show: 是否 plt.show()
    """
    if not series_df_by_name:
        return
    fig, ax = plt.subplots(figsize=(14, 7))
    colors = ["#2196F3", "#FF9800", "#4CAF50", "#9C27B0"]
    benchmark_plotted = False
    for idx, (name, df) in enumerate(series_df_by_name.items()):
        if df.empty or "strategy_cum_return" not in df.columns:
            continue
        ax.plot(
            df.index,
            df["strategy_cum_return"],
            label=name,
            linewidth=1.5,
            color=colors[idx % len(colors)],
        )
        if not benchmark_plotted and "benchmark_cum_return" in df.columns:
            ax.plot(
                df.index,
                df["benchmark_cum_return"],
                label="Buy & Hold (Benchmark)",
                linewidth=1.5,
                color="#888888",
            )
            benchmark_plotted = True
    ax.set_title(title or "Strategy Comparison", fontsize=14)
    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Cumulative Return (starting from 1)", fontsize=12)
    ax.legend(fontsize=11)
    ax.grid(alpha=0.3)
    ax.xaxis.set_major_locator(mdates.YearLocator(2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"Chart saved: {save_path}")
    if show:
        plt.show()
    else:
        plt.close(fig)
