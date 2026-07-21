"""
metrics.py
----------
Standard risk-adjusted performance metrics computed from an equity curve
and trade log. These are the numbers a reviewer actually asks about —
raw return alone says nothing about how much risk was taken to get it.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def compute_returns(equity_curve: pd.Series) -> pd.Series:
    return equity_curve.pct_change().dropna()


def sharpe_ratio(returns: pd.Series, periods_per_year: int = 252, risk_free: float = 0.0) -> float:
    excess = returns - risk_free / periods_per_year
    if excess.std() == 0:
        return 0.0
    return float(np.sqrt(periods_per_year) * excess.mean() / excess.std())


def sortino_ratio(returns: pd.Series, periods_per_year: int = 252, risk_free: float = 0.0) -> float:
    excess = returns - risk_free / periods_per_year
    downside = excess[excess < 0]
    downside_std = downside.std()
    if downside_std == 0 or np.isnan(downside_std):
        return 0.0
    return float(np.sqrt(periods_per_year) * excess.mean() / downside_std)


def max_drawdown(equity_curve: pd.Series) -> float:
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1
    return float(drawdown.min())


def cagr(equity_curve: pd.Series, periods_per_year: int = 252) -> float:
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0]
    years = len(equity_curve) / periods_per_year
    if years <= 0:
        return 0.0
    return float(total_return ** (1 / years) - 1)


def trade_stats(trades_df: pd.DataFrame) -> dict:
    if trades_df.empty:
        return {"num_trades": 0, "win_rate": 0.0, "profit_factor": 0.0, "avg_win": 0.0, "avg_loss": 0.0}
    wins = trades_df[trades_df["pnl"] > 0]
    losses = trades_df[trades_df["pnl"] <= 0]
    gross_profit = wins["pnl"].sum()
    gross_loss = -losses["pnl"].sum()
    return {
        "num_trades": int(len(trades_df)),
        "win_rate": float(len(wins) / len(trades_df)),
        "profit_factor": float(gross_profit / gross_loss) if gross_loss > 0 else float("inf"),
        "avg_win": float(wins["pnl"].mean()) if len(wins) else 0.0,
        "avg_loss": float(losses["pnl"].mean()) if len(losses) else 0.0,
    }


def summary(equity_curve: pd.Series, trades_df: pd.DataFrame) -> dict:
    returns = compute_returns(equity_curve)
    stats = {
        "total_return_pct": float((equity_curve.iloc[-1] / equity_curve.iloc[0] - 1) * 100),
        "cagr_pct": cagr(equity_curve) * 100,
        "sharpe_ratio": sharpe_ratio(returns),
        "sortino_ratio": sortino_ratio(returns),
        "max_drawdown_pct": max_drawdown(equity_curve) * 100,
    }
    stats.update(trade_stats(trades_df))
    return stats
