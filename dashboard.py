"""
dashboard.py
------------
Interactive Streamlit front-end for the backtester — adjust the entry/exit
lookback windows and risk-per-trade live, and see the equity curve,
drawdown, and metrics update.

Run with:
    streamlit run dashboard.py
"""

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from data_loader import load_csv
from strategy import DonchianBreakout
from backtest import run_backtest
import metrics as m

st.set_page_config(page_title="Breakout Strategy Backtester", layout="wide")
st.title("Donchian Breakout Backtester")
st.caption("Systematic trend-following: long new N-day highs, short new N-day lows, "
           "ATR-based stops and position sizing. Bundled sample: AAPL daily, Feb 2015 - Feb 2017.")

with st.sidebar:
    st.header("Strategy parameters")
    entry_window = st.slider("Entry breakout window (days)", 10, 60, 20)
    exit_window = st.slider("Exit breakout window (days)", 5, 40, 10)
    stop_atr_mult = st.slider("Stop-loss distance (x ATR)", 1.0, 4.0, 2.0, step=0.5)
    risk_per_trade = st.slider("Risk per trade (% of equity)", 0.25, 3.0, 1.0, step=0.25) / 100
    allow_short = st.checkbox("Allow short trades", value=True)

df = load_csv("data/aapl_sample.csv")
strat = DonchianBreakout(entry_window=entry_window, exit_window=exit_window,
                          stop_atr_mult=stop_atr_mult, allow_short=allow_short)
prepared = strat.prepare(df)
result = run_backtest(prepared, risk_per_trade=risk_per_trade)
trades_df = result.trades_df
stats = m.summary(result.equity_curve, trades_df)

bh_prices = df.loc[result.equity_curve.index, "close"]
benchmark = 100_000.0 * (bh_prices / bh_prices.iloc[0])
bh_return = (benchmark.iloc[-1] / benchmark.iloc[0] - 1) * 100

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total return", f"{stats['total_return_pct']:.1f}%", f"{stats['total_return_pct'] - bh_return:.1f}pp vs B&H")
col2.metric("Sharpe ratio", f"{stats['sharpe_ratio']:.2f}")
col3.metric("Max drawdown", f"{stats['max_drawdown_pct']:.1f}%")
col4.metric("Win rate", f"{stats['win_rate'] * 100:.0f}%")
col5.metric("Trades", f"{stats['num_trades']}")

fig, ax = plt.subplots(figsize=(11, 4.5))
ax.plot(result.equity_curve.index, result.equity_curve.values, label="Strategy", linewidth=1.6)
ax.plot(benchmark.index, benchmark.values, label="Buy & hold AAPL", linewidth=1.2, linestyle="--")
ax.legend()
ax.set_ylabel("Portfolio value ($)")
st.pyplot(fig)

st.subheader("Trade log")
st.dataframe(trades_df, use_container_width=True)

st.subheader("Full metrics")
st.json(stats)
