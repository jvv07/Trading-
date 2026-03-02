"""
Market data abstraction layer.
DATA_SOURCE env var selects the backend: 'yfinance' (default) or 'ibkr'.
"""

import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

_SOURCE = (os.environ.get("DATA_SOURCE") or "yfinance").lower()


def get_price(symbol: str) -> float:
    """Return latest price for a symbol."""
    if _SOURCE == "ibkr":
        return _ibkr_price(symbol)
    return _yf_price(symbol)


def get_history(symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
    """Return OHLCV history as DataFrame."""
    if _SOURCE == "ibkr":
        return _ibkr_history(symbol, period, interval)
    return _yf_history(symbol, period, interval)


# ── yfinance backend ─────────────────────────────────────────────────────────

def _yf_price(symbol: str) -> float:
    import yfinance as yf
    ticker = yf.Ticker(symbol)
    info = ticker.fast_info
    return float(info.last_price)


def _yf_history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    import yfinance as yf
    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=True)
    df.index = pd.to_datetime(df.index)
    return df


# ── IBKR backend (ib_insync) ─────────────────────────────────────────────────

def _ibkr_price(symbol: str) -> float:
    ib = _ibkr_connect()
    from ib_insync import Stock
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)
    ticker = ib.reqMktData(contract, "", False, False)
    ib.sleep(1)
    price = ticker.last or ticker.close
    ib.disconnect()
    return float(price)


def _ibkr_history(symbol: str, period: str, interval: str) -> pd.DataFrame:
    ib = _ibkr_connect()
    from ib_insync import Stock, util
    _period_map = {"1d": "1 D", "5d": "5 D", "1mo": "1 M", "3mo": "3 M",
                   "6mo": "6 M", "1y": "1 Y", "2y": "2 Y", "5y": "5 Y"}
    _bar_map = {"1m": "1 min", "5m": "5 mins", "15m": "15 mins",
                "1h": "1 hour", "1d": "1 day"}
    contract = Stock(symbol, "SMART", "USD")
    ib.qualifyContracts(contract)
    bars = ib.reqHistoricalData(
        contract,
        endDateTime="",
        durationStr=_period_map.get(period, "1 Y"),
        barSizeSetting=_bar_map.get(interval, "1 day"),
        whatToShow="TRADES",
        useRTH=True,
    )
    ib.disconnect()
    return util.df(bars).set_index("date")


def _ibkr_connect():
    from ib_insync import IB
    ib = IB()
    ib.connect(
        os.environ.get("IBKR_HOST", "127.0.0.1"),
        int(os.environ.get("IBKR_PORT", 7497)),
        clientId=int(os.environ.get("IBKR_CLIENT_ID", 1)),
    )
    return ib
