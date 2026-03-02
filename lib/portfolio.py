"""
Portfolio computation helpers — derive positions and equity curve from trades.
"""

import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
from lib.supabase_client import get_client, SOLO_USER_ID


def get_trades_df() -> pd.DataFrame:
    client = get_client()
    res = client.table("trades").select("*").eq("user_id", SOLO_USER_ID).order("executed_at").execute()
    if not res.data:
        return pd.DataFrame()
    df = pd.DataFrame(res.data)
    df["executed_at"] = pd.to_datetime(df["executed_at"])
    df["quantity"] = df["quantity"].astype(float)
    df["price"] = df["price"].astype(float)
    df["commission"] = df["commission"].astype(float)
    df["notional"] = df["quantity"] * df["price"]
    return df


def compute_positions(trades_df: pd.DataFrame) -> pd.DataFrame:
    """AVCO method — returns open positions DataFrame."""
    if trades_df.empty:
        return pd.DataFrame()

    positions: dict = {}
    realized: dict = {}

    for _, t in trades_df.sort_values("executed_at").iterrows():
        sym = t["symbol"]
        if sym not in positions:
            positions[sym] = {"qty": 0.0, "avg_cost": 0.0}
            realized[sym] = 0.0

        p = positions[sym]
        if t["side"] == "buy":
            new_qty = p["qty"] + t["quantity"]
            p["avg_cost"] = (p["qty"] * p["avg_cost"] + t["quantity"] * t["price"]) / new_qty
            p["qty"] = new_qty
        elif t["side"] == "sell":
            if p["qty"] > 0:
                realized[sym] += (t["price"] - p["avg_cost"]) * t["quantity"] - t["commission"]
            p["qty"] = max(0.0, p["qty"] - t["quantity"])
            if p["qty"] == 0:
                p["avg_cost"] = 0.0

    rows = [
        {
            "symbol": sym,
            "quantity": p["qty"],
            "avg_cost": p["avg_cost"],
            "cost_basis": p["qty"] * p["avg_cost"],
            "realized_pnl": realized.get(sym, 0.0),
        }
        for sym, p in positions.items()
        if p["qty"] > 1e-6
    ]
    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(ttl=300)
def fetch_current_prices(symbols: list) -> dict:
    """Batch fetch latest prices. Returns {symbol: price}."""
    if not symbols:
        return {}
    try:
        tickers = yf.Tickers(" ".join(symbols))
        return {s: tickers.tickers[s].fast_info.last_price for s in symbols}
    except Exception:
        # Fallback: individual fetches
        prices = {}
        for s in symbols:
            try:
                prices[s] = yf.Ticker(s).fast_info.last_price
            except Exception:
                prices[s] = None
        return prices


@st.cache_data(ttl=3600)
def build_equity_curve(trades_df_json: str) -> pd.Series:
    """
    Build daily portfolio equity curve using historical prices.
    Accepts JSON-serialized trades df to enable st.cache_data hashing.
    """
    trades_df = pd.read_json(trades_df_json)
    if trades_df.empty:
        return pd.Series(dtype=float)

    trades_df["executed_at"] = pd.to_datetime(trades_df["executed_at"])
    trades_df["quantity"] = trades_df["quantity"].astype(float)
    trades_df["price"] = trades_df["price"].astype(float)

    symbols = trades_df["symbol"].unique().tolist()
    start = trades_df["executed_at"].min().strftime("%Y-%m-%d")

    raw = yf.download(symbols, start=start, auto_adjust=True, progress=False)
    if raw.empty:
        return pd.Series(dtype=float)

    if isinstance(raw.columns, pd.MultiIndex):
        closes = raw["Close"]
    else:
        closes = raw[["Close"]]
        closes.columns = symbols

    dates = closes.index
    equity_values = []

    for date in dates:
        trades_up_to = trades_df[trades_df["executed_at"].dt.date <= date.date()]
        positions = compute_positions(trades_up_to)
        if positions.empty:
            equity_values.append(0.0)
            continue
        total = 0.0
        for _, row in positions.iterrows():
            sym = row["symbol"]
            if sym in closes.columns:
                price_series = closes[sym].loc[:date].dropna()
                if not price_series.empty:
                    total += row["quantity"] * float(price_series.iloc[-1])
        equity_values.append(total)

    return pd.Series(equity_values, index=dates, name="Portfolio")
