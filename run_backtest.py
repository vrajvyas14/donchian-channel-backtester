"""
run_backtest.py
---------------
Ties the pipeline together: load data -> compute strategy signals -> run
the backtest -> compute metrics -> save a benchmark-compared equity chart,
a drawdown chart, the trade log, and a metrics summary.

Usage (bundled sample data, works offline):
    python run_backtest.py

Usage (live data via yfinance, needs internet + `pip install yfinance`):
    python run_backtest.py --ticker MSFT --start 2018-01-01 --end 2024-01-01 --live
"""

from __future__ import annotations
import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from data_loader import load_csv, load_yfinance
from strategy import DonchianBreakout
from backtest import run_backtest
import metrics as m


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--start", default="2015-02-17")
    parser.add_argument("--end", default="2017-02-16")
    parser.add_argument("--live", action="store_true", help="pull live data via yfinance instead of the bundled CSV")
    parser.add_argument("--entry-window", type=int, default=20)
    parser.add_argument("--exit-window", type=int, default=10)
    parser.add_argument("--risk-per-trade", type=float, default=0.01)
    parser.add_argument("--capital", type=float, default=100_000.0)
    parser.add_argument("--outdir", default="output")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    if args.live:
        df = load_yfinance(args.ticker, args.start, args.end)
    else:
        df = load_csv("data/aapl_sample.csv")

    strat = DonchianBreakout(entry_window=args.entry_window, exit_window=args.exit_window)
    prepared = strat.prepare(df)

    result = run_backtest(prepared, initial_capital=args.capital, risk_per_trade=args.risk_per_trade)
    trades_df = result.trades_df
    stats = m.summary(result.equity_curve, trades_df)

    # Buy-and-hold benchmark over the same tradeable window, same starting capital
    bh_prices = df.loc[result.equity_curve.index, "close"]
    benchmark = args.capital * (bh_prices / bh_prices.iloc[0])

    # --- Console summary ---
    print(f"\n{args.ticker} Donchian Breakout ({args.entry_window}/{args.exit_window}) "
          f"| {result.equity_curve.index[0].date()} -> {result.equity_curve.index[-1].date()}\n")
    for k, v in stats.items():
        label = k.replace("_", " ")
        print(f"  {label:22s}: {v:,.3f}" if isinstance(v, float) else f"  {label:22s}: {v}")
    bh_return = (benchmark.iloc[-1] / benchmark.iloc[0] - 1) * 100
    print(f"  {'buy_and_hold return %':22s}: {bh_return:,.2f}")

    # --- Save outputs ---
    with open(os.path.join(args.outdir, "metrics_summary.json"), "w") as f:
        json.dump({**stats, "buy_and_hold_return_pct": bh_return}, f, indent=2)
    trades_df.to_csv(os.path.join(args.outdir, "trades.csv"), index=False)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(result.equity_curve.index, result.equity_curve.values, label="Donchian breakout strategy", linewidth=1.6)
    ax.plot(benchmark.index, benchmark.values, label=f"Buy & hold {args.ticker}", linewidth=1.2, linestyle="--")
    ax.set_title(f"Equity curve: Donchian breakout vs. buy & hold ({args.ticker})")
    ax.set_ylabel("Portfolio value ($)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(args.outdir, "equity_curve.png"), dpi=150)

    running_max = result.equity_curve.cummax()
    drawdown = (result.equity_curve / running_max - 1) * 100
    fig2, ax2 = plt.subplots(figsize=(10, 3.2))
    ax2.fill_between(drawdown.index, drawdown.values, 0, color="firebrick", alpha=0.6)
    ax2.set_title("Strategy drawdown (%)")
    ax2.set_ylabel("Drawdown %")
    fig2.tight_layout()
    fig2.savefig(os.path.join(args.outdir, "drawdown.png"), dpi=150)

    print(f"\nSaved: {args.outdir}/equity_curve.png, {args.outdir}/drawdown.png, "
          f"{args.outdir}/trades.csv, {args.outdir}/metrics_summary.json")


if __name__ == "__main__":
    main()
