"""
strategy.py
-----------
Donchian-channel breakout system (the "Turtle Trading" family of trend
following rules): go long when price breaks out to a new N-day high,
go short when it breaks to a new N-day low, and exit on a breakout of
the opposite M-day channel (M < N) or a volatility stop.

This module only computes indicators and signals — it does not simulate
money. That's backtest.py's job. Keeping them separate means you can
unit-test the signal logic without needing a portfolio simulator, and
swap in a different strategy (e.g. intraday Opening Range Breakout)
without touching the backtest engine at all.
"""

from __future__ import annotations
import pandas as pd


def average_true_range(df: pd.DataFrame, window: int = 20) -> pd.Series:
    """Wilder's Average True Range — used for stop placement and position sizing."""
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def donchian_channels(df: pd.DataFrame, entry_window: int, exit_window: int) -> pd.DataFrame:
    """
    Rolling highs/lows used as breakout thresholds. Shifted by 1 day so
    that "today's breakout" is measured against the prior N days, not
    including today's own bar (avoiding lookahead bias).
    """
    out = pd.DataFrame(index=df.index)
    out["entry_high"] = df["high"].rolling(entry_window).max().shift(1)
    out["entry_low"] = df["low"].rolling(entry_window).min().shift(1)
    out["exit_high"] = df["high"].rolling(exit_window).max().shift(1)
    out["exit_low"] = df["low"].rolling(exit_window).min().shift(1)
    return out


class DonchianBreakout:
    """
    Parameters
    ----------
    entry_window : lookback (days) for the breakout that opens a position
    exit_window  : lookback (days) for the opposite breakout that closes it
    atr_window   : lookback (days) for the ATR used in stops/position sizing
    stop_atr_mult: stop-loss distance from entry, in multiples of ATR
    allow_short  : if False, only takes long trades (simpler long-only variant)
    """

    def __init__(self, entry_window: int = 20, exit_window: int = 10,
                 atr_window: int = 20, stop_atr_mult: float = 2.0,
                 allow_short: bool = True):
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.atr_window = atr_window
        self.stop_atr_mult = stop_atr_mult
        self.allow_short = allow_short

    def prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return df enriched with the columns the backtest engine needs."""
        out = df.copy()
        channels = donchian_channels(df, self.entry_window, self.exit_window)
        out = out.join(channels)
        out["atr"] = average_true_range(df, self.atr_window)
        out["long_entry_signal"] = out["close"] > out["entry_high"]
        out["short_entry_signal"] = (out["close"] < out["entry_low"]) & self.allow_short
        out["long_exit_signal"] = out["close"] < out["exit_low"]
        out["short_exit_signal"] = out["close"] > out["exit_high"]
        return out.dropna(subset=["entry_high", "entry_low", "atr"])
