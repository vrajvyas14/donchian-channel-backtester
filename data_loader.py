"""
data_loader.py
--------------
Loads OHLCV price data for the backtester from either:
  1. A local CSV (bundled sample: data/aapl_sample.csv, real AAPL daily
     data, Feb 2015 - Feb 2017)
  2. Yahoo Finance via yfinance (for any ticker/date range), when you're
     running this with a normal internet connection.

Both paths return the same standardised DataFrame shape:
    index: DatetimeIndex named 'date'
    columns: ['open', 'high', 'low', 'close', 'volume']
so the rest of the pipeline (strategy, backtest, metrics) never needs to
know which source the data came from.
"""

from __future__ import annotations
import pandas as pd


REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]


def _standardise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")
    df.index.name = "date"
    df = df.sort_index()
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Data is missing required columns: {missing}")
    return df[REQUIRED_COLUMNS].astype(float)


def load_csv(path: str) -> pd.DataFrame:
    """Load OHLCV data from a local CSV with a 'date' column."""
    df = pd.read_csv(path)
    return _standardise(df)


def load_yfinance(ticker: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    """
    Load OHLCV data live from Yahoo Finance. Requires `pip install yfinance`
    and an internet connection (this will not work in a network-sandboxed
    environment — use load_csv() there instead).

    interval: '1d' for daily bars. Yahoo also supports intraday intervals
    ('5m', '15m', '30m', '60m') for the last ~60 days, which is what you'd
    use to extend this into a genuine intraday Opening-Range-Breakout
    version instead of the daily Donchian version implemented here.
    """
    import yfinance as yf  # imported lazily so the CSV path never needs it

    raw = yf.download(ticker, start=start, end=end, interval=interval, progress=False)
    raw = raw.reset_index()
    raw = raw.rename(columns={raw.columns[0]: "date"})
    raw.columns = [str(c[0]).lower() if isinstance(c, tuple) else str(c).lower() for c in raw.columns]
    return _standardise(raw)
