"""
Vectorized backtesting engine.
Supports: SMA Cross, RSI Reversion, Bollinger Bands, MACD Cross, Momentum.
"""

import pandas as pd
import numpy as np
import yfinance as yf
from lib.indicators import sma, ema, rsi, macd, bollinger_bands
from lib import metrics as m


STRATEGIES = {
    "SMA Crossover": {
        "description": "Buy when fast SMA crosses above slow SMA. Sell on reverse cross.",
        "params": {
            "fast_period": {"type": "int", "default": 20, "min": 5, "max": 100, "label": "Fast SMA Period"},
            "slow_period": {"type": "int", "default": 50, "min": 10, "max": 300, "label": "Slow SMA Period"},
        },
    },
    "RSI Reversion": {
        "description": "Buy when RSI crosses below oversold. Sell when RSI crosses above overbought.",
        "params": {
            "period":    {"type": "int",   "default": 14,  "min": 5,  "max": 50,  "label": "RSI Period"},
            "oversold":  {"type": "int",   "default": 30,  "min": 10, "max": 45,  "label": "Oversold Threshold"},
            "overbought":{"type": "int",   "default": 70,  "min": 55, "max": 90,  "label": "Overbought Threshold"},
        },
    },
    "Bollinger Reversion": {
        "description": "Buy when price touches lower band. Sell when price returns to middle band.",
        "params": {
            "period":  {"type": "int",   "default": 20,  "min": 5,  "max": 100, "label": "Period"},
            "std_dev": {"type": "float", "default": 2.0, "min": 1.0,"max": 4.0, "label": "Std Dev"},
        },
    },
    "MACD Crossover": {
        "description": "Buy when MACD line crosses above signal line. Sell on reverse.",
        "params": {
            "fast":   {"type": "int", "default": 12, "min": 5,  "max": 50, "label": "Fast EMA"},
            "slow":   {"type": "int", "default": 26, "min": 10, "max": 100,"label": "Slow EMA"},
            "signal": {"type": "int", "default": 9,  "min": 3,  "max": 30, "label": "Signal EMA"},
        },
    },
    "Momentum": {
        "description": "Buy when N-day return is positive. Hold for M days.",
        "params": {
            "lookback":    {"type": "int", "default": 20, "min": 5,  "max": 252, "label": "Lookback Period"},
            "hold_period": {"type": "int", "default": 20, "min": 1,  "max": 126, "label": "Hold Period (days)"},
            "threshold":   {"type": "float","default": 0.0,"min": -0.1,"max": 0.2,"label": "Return Threshold"},
        },
    },
}


def _signal_sma_cross(df, params):
    fast = sma(df["Close"], params["fast_period"])
    slow = sma(df["Close"], params["slow_period"])
    signal = (fast > slow).astype(int)
    return signal


def _signal_rsi(df, params):
    r = rsi(df["Close"], params["period"])
    signal = pd.Series(0, index=df.index)
    in_trade = False
    for i in range(len(r)):
        if pd.isna(r.iloc[i]):
            signal.iloc[i] = 0
            continue
        if not in_trade and r.iloc[i] < params["oversold"]:
            in_trade = True
        elif in_trade and r.iloc[i] > params["overbought"]:
            in_trade = False
        signal.iloc[i] = 1 if in_trade else 0
    return signal


def _signal_bollinger(df, params):
    upper, middle, lower = bollinger_bands(df["Close"], params["period"], params["std_dev"])
    signal = pd.Series(0, index=df.index)
    in_trade = False
    for i in range(len(df)):
        close = df["Close"].iloc[i]
        if pd.isna(lower.iloc[i]):
            continue
        if not in_trade and close <= lower.iloc[i]:
            in_trade = True
        elif in_trade and close >= middle.iloc[i]:
            in_trade = False
        signal.iloc[i] = 1 if in_trade else 0
    return signal


def _signal_macd(df, params):
    macd_line, signal_line, _ = macd(df["Close"], params["fast"], params["slow"], params["signal"])
    above = (macd_line > signal_line).astype(int)
    return above


def _signal_momentum(df, params):
    ret = df["Close"].pct_change(params["lookback"])
    raw = (ret > params["threshold"]).astype(int)
    # Hold for hold_period days after signal
    signal = pd.Series(0, index=df.index)
    hold_remaining = 0
    for i in range(len(raw)):
        if raw.iloc[i] == 1:
            hold_remaining = params["hold_period"]
        if hold_remaining > 0:
            signal.iloc[i] = 1
            hold_remaining -= 1
    return signal


_SIGNAL_FNS = {
    "SMA Crossover": _signal_sma_cross,
    "RSI Reversion": _signal_rsi,
    "Bollinger Reversion": _signal_bollinger,
    "MACD Crossover": _signal_macd,
    "Momentum": _signal_momentum,
}


def run_backtest(
    symbol: str,
    strategy_name: str,
    params: dict,
    start_date: str,
    end_date: str,
    initial_capital: float = 10_000.0,
) -> dict:
    df = yf.download(symbol, start=start_date, end=end_date, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No data returned for {symbol}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.dropna(inplace=True)

    signal_fn = _SIGNAL_FNS[strategy_name]
    df["signal"] = signal_fn(df, params)
    df["position"] = df["signal"].shift(1).fillna(0)

    df["daily_return"] = df["Close"].pct_change()
    df["strategy_return"] = df["position"] * df["daily_return"]
    df["equity"] = initial_capital * (1 + df["strategy_return"].fillna(0)).cumprod()
    df["bh_equity"] = initial_capital * (1 + df["daily_return"].fillna(0)).cumprod()

    trades = _extract_trades(df)
    trade_pnls = pd.Series([t["pnl"] for t in trades]) if trades else pd.Series(dtype=float)

    stats = m.summary(
        df["strategy_return"].dropna(),
        df["equity"].dropna(),
        trade_pnls,
    )
    bh_return = (df["bh_equity"].iloc[-1] / initial_capital - 1) * 100
    stats["B&H Return"] = f"{bh_return:.2f}%"
    stats["# Trades"] = str(len(trades))

    return {
        "df": df,
        "trades": trades,
        "metrics": stats,
        "equity": df["equity"],
        "bh_equity": df["bh_equity"],
        "returns": df["strategy_return"],
    }


def _extract_trades(df: pd.DataFrame) -> list:
    trades = []
    in_trade = False
    entry_date = entry_price = None

    for date, row in df.iterrows():
        pos = row["position"]
        close = row["Close"]
        if pos == 1 and not in_trade:
            in_trade = True
            entry_date = date
            entry_price = close
        elif pos == 0 and in_trade:
            in_trade = False
            hold = (date - entry_date).days
            ret = (close - entry_price) / entry_price
            trades.append({
                "entry_date": entry_date.date(),
                "exit_date": date.date(),
                "entry_price": round(float(entry_price), 4),
                "exit_price": round(float(close), 4),
                "return_pct": round(ret * 100, 2),
                "pnl": round(float(close - entry_price), 4),
                "holding_days": hold,
            })

    if in_trade:
        last_date = df.index[-1]
        last_close = df["Close"].iloc[-1]
        ret = (last_close - entry_price) / entry_price
        trades.append({
            "entry_date": entry_date.date(),
            "exit_date": last_date.date(),
            "entry_price": round(float(entry_price), 4),
            "exit_price": round(float(last_close), 4),
            "return_pct": round(ret * 100, 2),
            "pnl": round(float(last_close - entry_price), 4),
            "holding_days": (last_date - entry_date).days,
            "open": True,
        })

    return trades
