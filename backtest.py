"""
backtest.py
-----------
Event-driven (day-by-day) backtest engine. Deliberately not vectorised:
stop-losses and position sizing are path-dependent (what happens on day
N depends on whether day N-1 stopped you out), so a day-by-day loop is
the correct tool here, not a shortcut — vectorising this would silently
produce wrong results around stop-outs.

Execution convention (to avoid lookahead bias):
  - A breakout is detected using day T's close vs. the Donchian channel.
  - The resulting trade is executed at day T+1's OPEN, since in reality
    you can't act on a closing price until the next session.
  - Stop-losses are checked against each day's high/low and, if hit,
    filled at the stop price that same day (a common simplifying
    assumption — real fills would have slippage).
"""

from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd


@dataclass
class Trade:
    direction: str        # 'long' or 'short'
    entry_date: pd.Timestamp
    entry_price: float
    shares: float
    stop_price: float
    exit_date: pd.Timestamp = None
    exit_price: float = None
    exit_reason: str = None

    @property
    def pnl(self) -> float:
        if self.exit_price is None:
            return 0.0
        sign = 1 if self.direction == "long" else -1
        return sign * (self.exit_price - self.entry_price) * self.shares


@dataclass
class BacktestResult:
    equity_curve: pd.Series
    trades: list = field(default_factory=list)

    @property
    def trades_df(self) -> pd.DataFrame:
        rows = [{
            "direction": t.direction, "entry_date": t.entry_date, "entry_price": t.entry_price,
            "shares": t.shares, "stop_price": t.stop_price, "exit_date": t.exit_date,
            "exit_price": t.exit_price, "exit_reason": t.exit_reason, "pnl": t.pnl,
        } for t in self.trades]
        return pd.DataFrame(rows)


def run_backtest(df: pd.DataFrame, initial_capital: float = 100_000.0,
                  risk_per_trade: float = 0.01) -> BacktestResult:
    """
    df must already be enriched by Strategy.prepare() — needs entry_high,
    entry_low, exit_high, exit_low, atr, and the *_signal columns.

    risk_per_trade: fraction of current equity risked per trade (the
    distance from entry to stop = stop_atr_mult * ATR represents this
    fraction of equity). 0.01 = risk 1% of equity per trade, the standard
    conservative default used in most systematic trend-following systems.
    """
    cash = initial_capital
    position: Trade | None = None
    equity_curve = {}
    trades: list[Trade] = []

    dates = df.index.to_list()
    pending_entry = None  # (direction, stop_atr_mult * atr) queued from yesterday's signal

    for i, today in enumerate(dates):
        row = df.loc[today]

        # 1. Execute any entry queued from yesterday's signal, at today's open
        if position is None and pending_entry is not None:
            direction, atr_at_signal, stop_mult = pending_entry
            entry_price = row["open"]
            risk_amount = cash * risk_per_trade
            stop_distance = stop_mult * atr_at_signal
            shares = 0.0
            if stop_distance > 0:
                shares = risk_amount / stop_distance
                shares = min(shares, cash / entry_price) if entry_price > 0 else 0.0
            if shares > 0:
                stop_price = entry_price - stop_distance if direction == "long" else entry_price + stop_distance
                position = Trade(direction, today, entry_price, shares, stop_price)
            pending_entry = None

        # 2. Manage an open position: stop-loss, then signal-based exit
        if position is not None:
            hit_stop = (
                row["low"] <= position.stop_price if position.direction == "long"
                else row["high"] >= position.stop_price
            )
            signal_exit = (
                row["long_exit_signal"] if position.direction == "long"
                else row["short_exit_signal"]
            )
            if hit_stop:
                position.exit_date, position.exit_price, position.exit_reason = today, position.stop_price, "stop"
            elif signal_exit:
                position.exit_date, position.exit_price, position.exit_reason = today, row["close"], "signal"

            if position.exit_price is not None:
                cash += position.pnl
                trades.append(position)
                position = None

        # 3. Look for a new entry signal to queue for tomorrow (only while flat)
        if position is None and pending_entry is None:
            if row["long_entry_signal"]:
                pending_entry = ("long", row["atr"], 2.0)
            elif row["short_entry_signal"]:
                pending_entry = ("short", row["atr"], 2.0)

        # 4. Mark-to-market equity for today
        unrealised = position.pnl if position and position.exit_price is None and False else 0.0
        if position is not None and position.exit_price is None:
            sign = 1 if position.direction == "long" else -1
            unrealised = sign * (row["close"] - position.entry_price) * position.shares
        equity_curve[today] = cash + unrealised

    # Close any position still open at the end of the sample, at the last close
    if position is not None:
        last_date = dates[-1]
        position.exit_date = last_date
        position.exit_price = df.loc[last_date, "close"]
        position.exit_reason = "end_of_sample"
        cash += position.pnl
        trades.append(position)
        equity_curve[last_date] = cash

    return BacktestResult(equity_curve=pd.Series(equity_curve, name="equity"), trades=trades)
