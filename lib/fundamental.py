"""
Fundamental analysis module: data fetching, financial models, and scoring.
All fetch_* functions return safe empty defaults on error.
"""
from __future__ import annotations  # enables dict | None on Python 3.8/3.9

import os
import math
import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

from lib.universe import SECTORS

# ── Sector median tables ──────────────────────────────────────────────────────

SECTOR_PE_MEDIANS = {
    "Technology": 28,
    "Financials": 14,
    "Healthcare": 22,
    "Energy": 12,
    "Consumer Disc.": 20,
    "Consumer Discretionary": 20,
    "Consumer Staples": 18,
    "Industrials": 20,
    "Communication": 18,
    "Communication Services": 18,
    "Utilities": 16,
    "Real Estate": 35,
    "Materials": 15,
    "Basic Materials": 15,
}

SECTOR_EV_EBITDA_MEDIANS = {
    "Technology": 22,
    "Financials": 12,
    "Healthcare": 14,
    "Energy": 8,
    "Consumer Disc.": 12,
    "Consumer Discretionary": 12,
    "Consumer Staples": 13,
    "Industrials": 13,
    "Communication": 12,
    "Communication Services": 12,
    "Utilities": 13,
    "Real Estate": 18,
    "Materials": 10,
    "Basic Materials": 10,
}

# Maps yfinance sector names → our SECTORS dict keys
SECTOR_NAME_MAP = {
    "Financial Services":     "Financials",
    "Consumer Cyclical":      "Consumer Disc.",
    "Consumer Defensive":     "Consumer Staples",
    "Communication Services": "Communication",
    "Basic Materials":        "Materials",
    "Technology":             "Technology",
    "Healthcare":             "Healthcare",
    "Energy":                 "Energy",
    "Industrials":            "Industrials",
    "Utilities":              "Utilities",
    "Real Estate":            "Real Estate",
}


# ── Core helpers ──────────────────────────────────────────────────────────────

def get_fmp_key() -> str:
    try:
        k = st.secrets.get("FMP_API_KEY", "")
        if k:
            return k
    except Exception:
        pass
    return os.environ.get("FMP_API_KEY", "")


def safe_get(info: dict, key: str, default=None):
    try:
        v = info.get(key, default)
        return v if v is not None else default
    except Exception:
        return default


def format_large(n, prefix="$") -> str:
    if n is None:
        return "N/A"
    try:
        n = float(n)
        if math.isnan(n):
            return "N/A"
        if abs(n) >= 1e12:
            return f"{prefix}{n/1e12:.2f}T"
        if abs(n) >= 1e9:
            return f"{prefix}{n/1e9:.2f}B"
        if abs(n) >= 1e6:
            return f"{prefix}{n/1e6:.1f}M"
        return f"{prefix}{n:,.0f}"
    except Exception:
        return "N/A"


def bs_row(df: pd.DataFrame, *candidates):
    """Return first matching row from a DataFrame by index name."""
    if df is None or df.empty:
        return None
    for name in candidates:
        if name in df.index:
            return df.loc[name]
    return None


def _first_val(series):
    """Return the first non-null value from a Series, or None."""
    if series is None:
        return None
    try:
        vals = series.dropna()
        if vals.empty:
            return None
        return float(vals.iloc[0])
    except Exception:
        return None


def _get_df(ticker_obj, attrs: list) -> pd.DataFrame:
    """Try multiple attribute names for yfinance compatibility."""
    for attr in attrs:
        try:
            df = getattr(ticker_obj, attr, None)
            if df is not None and not df.empty:
                return df
        except Exception:
            continue
    return pd.DataFrame()


def _safe_df(df) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    return df


def _empty_financials() -> dict:
    return {k: pd.DataFrame() for k in [
        "annual_income", "quarterly_income",
        "annual_bs", "quarterly_bs",
        "annual_cf", "quarterly_cf",
    ]}


def get_sector_peers(sector: str, current_ticker: str) -> list:
    mapped = SECTOR_NAME_MAP.get(sector, sector)
    peers = SECTORS.get(mapped, [])
    return [p for p in peers if p != current_ticker][:6]


# ── Data fetching ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def fetch_info(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        # Supplement with fast_info for critical fields often missing on rate-limit
        try:
            fi = t.fast_info
            if not info.get("currentPrice") and not info.get("regularMarketPrice"):
                info["currentPrice"] = getattr(fi, "last_price", None)
            if not info.get("previousClose"):
                info["previousClose"] = getattr(fi, "previous_close", None)
            if not info.get("marketCap"):
                info["marketCap"] = getattr(fi, "market_cap", None)
            if not info.get("fiftyTwoWeekHigh"):
                info["fiftyTwoWeekHigh"] = getattr(fi, "year_high", None)
            if not info.get("fiftyTwoWeekLow"):
                info["fiftyTwoWeekLow"] = getattr(fi, "year_low", None)
            if not info.get("sharesOutstanding"):
                info["sharesOutstanding"] = getattr(fi, "shares", None)
        except Exception:
            pass
        return info
    except Exception:
        try:
            fi = yf.Ticker(ticker).fast_info
            return {
                "currentPrice":      getattr(fi, "last_price", None),
                "previousClose":     getattr(fi, "previous_close", None),
                "marketCap":         getattr(fi, "market_cap", None),
                "fiftyTwoWeekHigh":  getattr(fi, "year_high", None),
                "fiftyTwoWeekLow":   getattr(fi, "year_low", None),
                "sharesOutstanding": getattr(fi, "shares", None),
            }
        except Exception:
            return {}


@st.cache_data(ttl=3600)
def fetch_financials(ticker: str) -> dict:
    try:
        t = yf.Ticker(ticker)
        return {
            "annual_income":    _get_df(t, ["income_stmt", "financials"]),
            "quarterly_income": _get_df(t, ["quarterly_income_stmt", "quarterly_financials"]),
            "annual_bs":        _get_df(t, ["balance_sheet"]),
            "quarterly_bs":     _get_df(t, ["quarterly_balance_sheet"]),
            "annual_cf":        _get_df(t, ["cash_flow", "cashflow"]),
            "quarterly_cf":     _get_df(t, ["quarterly_cash_flow", "quarterly_cashflow"]),
        }
    except Exception:
        return _empty_financials()


@st.cache_data(ttl=3600)
def fetch_holders(ticker: str) -> dict:
    result = {"institutional": pd.DataFrame(), "major": pd.DataFrame(), "insider_tx": pd.DataFrame()}
    try:
        t = yf.Ticker(ticker)
        try:
            result["institutional"] = _safe_df(t.institutional_holders)
        except Exception:
            pass
        try:
            result["major"] = _safe_df(t.major_holders)
        except Exception:
            pass
        try:
            result["insider_tx"] = _safe_df(t.insider_transactions)
        except Exception:
            pass
    except Exception:
        pass
    return result


@st.cache_data(ttl=1800)
def fetch_market_data(ticker: str) -> dict:
    result = {
        "recommendations": pd.DataFrame(),
        "upgrades": pd.DataFrame(),
        "news": [],
        "dividends": pd.Series(dtype=float),
    }
    try:
        t = yf.Ticker(ticker)
        try:
            result["recommendations"] = _safe_df(t.recommendations)
        except Exception:
            pass
        try:
            result["upgrades"] = _safe_df(t.upgrades_downgrades)
        except Exception:
            pass
        try:
            result["news"] = t.news or []
        except Exception:
            pass
        try:
            result["dividends"] = t.dividends if t.dividends is not None else pd.Series(dtype=float)
        except Exception:
            pass
    except Exception:
        pass
    return result


@st.cache_data(ttl=7200)
def fetch_peer_info(peers_key: str) -> dict:
    peers = [p for p in peers_key.split(",") if p]
    result = {}
    for p in peers:
        try:
            result[p] = yf.Ticker(p).info or {}
        except Exception:
            result[p] = {}
    return result


@st.cache_data(ttl=3600)
def fetch_fmp(ticker: str) -> dict:
    key = get_fmp_key()
    if not key:
        return {}
    base = "https://financialmodelingprep.com/api/v3"
    result = {}
    try:
        import requests
        r = requests.get(
            f"{base}/analyst-estimates/{ticker}",
            params={"apikey": key, "limit": 4},
            timeout=6,
        )
        if r.ok:
            result["analyst_estimates"] = r.json()
    except Exception:
        pass
    try:
        import requests
        r = requests.get(
            f"{base}/key-metrics/{ticker}",
            params={"apikey": key, "limit": 4},
            timeout=6,
        )
        if r.ok:
            result["key_metrics"] = r.json()
    except Exception:
        pass
    try:
        import requests
        r = requests.get(
            f"{base}/insider-trading",
            params={"symbol": ticker, "apikey": key, "limit": 20},
            timeout=6,
        )
        if r.ok:
            result["insider_trading"] = r.json()
    except Exception:
        pass
    return result


# ── Financial models ──────────────────────────────────────────────────────────

def calc_wacc(info: dict) -> float:
    beta = float(safe_get(info, "beta", 1.0) or 1.0)
    beta = max(0.3, min(3.0, beta))
    re = 0.045 + beta * 0.055  # CAPM

    total_debt = float(safe_get(info, "totalDebt", 0) or 0)
    interest_expense = safe_get(info, "interestExpense", None)
    if interest_expense and total_debt > 0:
        rd = abs(float(interest_expense)) / total_debt
        rd = max(0.02, min(0.15, rd))
    else:
        rd = 0.05

    market_cap = float(safe_get(info, "marketCap", 0) or 0)
    E, D = market_cap, total_debt
    total = E + D
    if total == 0:
        return max(0.06, min(0.18, re))

    wacc = (E * re + D * rd * (1 - 0.21)) / total
    return max(0.06, min(0.18, wacc))


def calc_dcf(info: dict, financials: dict) -> dict | None:
    cf = financials.get("annual_cf", pd.DataFrame())

    ocf_row = bs_row(cf, "Operating Cash Flow", "Cash From Operations",
                     "Total Cash From Operating Activities", "Net Cash Provided By Operating Activities")
    cap_row = bs_row(cf, "Capital Expenditure", "Capital Expenditures",
                     "Purchase Of Property Plant And Equipment",
                     "Purchases Of Property Plant And Equipment")

    ocf = _first_val(ocf_row)
    capex = abs(_first_val(cap_row) or 0)

    if ocf is None:
        ocf = float(safe_get(info, "operatingCashflow", 0) or 0)
    if ocf <= 0:
        return None

    fcf = ocf - capex
    if fcf <= 0:
        return None

    shares = float(safe_get(info, "sharesOutstanding", 0) or 0)
    if shares <= 0:
        return None

    wacc = calc_wacc(info)
    rev_growth = safe_get(info, "revenueGrowth", None) or safe_get(info, "earningsGrowth", None) or 0.05
    growth1 = max(0.02, min(0.25, float(rev_growth)))
    growth2 = growth1 * 0.6
    terminal_growth = 0.025

    if wacc <= terminal_growth + 0.005:
        return None

    # Stage 1: years 1-5
    value = sum(fcf * (1 + growth1)**yr / (1 + wacc)**yr for yr in range(1, 6))

    # Stage 2: years 6-10
    fcf_s2 = fcf * (1 + growth1)**5
    value += sum(fcf_s2 * (1 + growth2)**yr / (1 + wacc)**(5 + yr) for yr in range(1, 6))

    # Terminal value
    fcf_term = fcf_s2 * (1 + growth2)**5 * (1 + terminal_growth)
    terminal_val = fcf_term / (wacc - terminal_growth)
    value += terminal_val / (1 + wacc)**10

    total_debt = float(safe_get(info, "totalDebt", 0) or 0)
    total_cash = float(safe_get(info, "totalCash", 0) or 0)
    equity_value = value + total_cash - total_debt
    fair_value = equity_value / shares

    return {
        "fair_value":   fair_value,
        "wacc":         wacc,
        "growth_rate":  growth1,
        "methodology":  f"2-stage DCF (g1={growth1*100:.1f}%, g2={growth2*100:.1f}%, WACC={wacc*100:.1f}%)",
    }


def calc_graham_number(info: dict) -> dict | None:
    eps = safe_get(info, "trailingEps", None)
    bv = safe_get(info, "bookValue", None)
    price = safe_get(info, "currentPrice", None) or safe_get(info, "regularMarketPrice", None)

    if not eps or eps <= 0 or not bv or bv <= 0:
        return None

    graham = math.sqrt(22.5 * float(eps) * float(bv))
    margin = (graham - float(price)) / graham if price and graham > 0 else None

    return {
        "graham_number":      graham,
        "margin_of_safety":   margin,
        "is_undervalued":     price is not None and float(price) < graham,
    }


def calc_ddm(info: dict) -> dict | None:
    div_rate = safe_get(info, "dividendRate", None)
    if not div_rate or div_rate <= 0:
        return None

    wacc = calc_wacc(info)
    g = 0.03  # terminal dividend growth

    if wacc <= g + 0.005:
        return None

    d1 = float(div_rate) * (1 + g)
    fair_value = d1 / (wacc - g)
    price = safe_get(info, "currentPrice", None) or safe_get(info, "regularMarketPrice", None)
    upside = (fair_value - float(price)) / float(price) if price else None

    return {
        "fair_value":  fair_value,
        "wacc":        wacc,
        "growth_rate": g,
        "methodology": f"DDM (g={g*100:.1f}%, WACC={wacc*100:.1f}%)",
        "upside":      upside,
    }


def calc_altman_z(info: dict, financials: dict) -> dict | None:
    try:
        bs = financials.get("annual_bs", pd.DataFrame())
        inc = financials.get("annual_income", pd.DataFrame())

        if bs.empty or inc.empty:
            return None

        total_assets = _first_val(bs_row(bs, "Total Assets"))
        if not total_assets or total_assets == 0:
            return None

        curr_assets = _first_val(bs_row(bs, "Current Assets", "Total Current Assets"))
        curr_liab   = _first_val(bs_row(bs, "Current Liabilities", "Total Current Liabilities"))
        working_cap = (curr_assets or 0) - (curr_liab or 0)
        X1 = working_cap / total_assets

        ret_earn = _first_val(bs_row(bs, "Retained Earnings"))
        X2 = (ret_earn or 0) / total_assets

        ebit = _first_val(bs_row(inc, "EBIT", "Operating Income", "Ebit"))
        if ebit is None:
            net_inc  = _first_val(bs_row(inc, "Net Income"))
            tax      = _first_val(bs_row(inc, "Tax Provision", "Income Tax Expense"))
            interest = _first_val(bs_row(inc, "Interest Expense", "Net Interest Income"))
            ebit = (net_inc or 0) + abs(tax or 0) + abs(interest or 0)
        X3 = (ebit or 0) / total_assets

        market_cap = float(safe_get(info, "marketCap", 0) or 0)
        total_liab = _first_val(bs_row(bs,
            "Total Liabilities Net Minority Interest", "Total Liabilities",
            "Total Liabilities And Stockholders Equity"))
        X4 = market_cap / (total_liab or 1)

        revenue = _first_val(bs_row(inc, "Total Revenue", "Revenue"))
        X5 = (revenue or 0) / total_assets

        Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5

        if Z > 2.99:
            zone, color = "Safe", "#00d4aa"
        elif Z > 1.81:
            zone, color = "Grey", "#f1c14e"
        else:
            zone, color = "Distress", "#ff4b4b"

        return {
            "z_score":    Z,
            "zone":       zone,
            "color":      color,
            "components": {"X1 (WC/TA)": X1, "X2 (RE/TA)": X2,
                           "X3 (EBIT/TA)": X3, "X4 (MCap/TL)": X4,
                           "X5 (Rev/TA)": X5},
        }
    except Exception:
        return None


def calc_relative_valuation(info: dict) -> dict:
    sector = safe_get(info, "sector", "")
    mapped = SECTOR_NAME_MAP.get(sector, sector)
    pe_median = SECTOR_PE_MEDIANS.get(mapped, 20)
    ev_median = SECTOR_EV_EBITDA_MEDIANS.get(mapped, 14)

    eps = safe_get(info, "trailingEps", None)
    pe_fair = float(pe_median) * float(eps) if eps and float(eps) > 0 else None

    ebitda = safe_get(info, "ebitda", None)
    shares = safe_get(info, "sharesOutstanding", None)
    total_debt = float(safe_get(info, "totalDebt", 0) or 0)
    total_cash = float(safe_get(info, "totalCash", 0) or 0)
    evebitda_fair = None
    if ebitda and float(ebitda) > 0 and shares and float(shares) > 0:
        implied_ev = ev_median * float(ebitda)
        equity_val = implied_ev - total_debt + total_cash
        evebitda_fair = equity_val / float(shares)

    return {
        "pe_fair_value":      pe_fair,
        "evebitda_fair_value": evebitda_fair,
        "pe_median":          pe_median,
        "ev_median":          ev_median,
        "sector":             mapped,
    }


# ── Scoring helpers ───────────────────────────────────────────────────────────

def _sig(text: str, passed, detail: str = "") -> dict:
    return {"text": text, "passed": passed, "detail": detail}


# ── Value score ───────────────────────────────────────────────────────────────

def score_value(info: dict, financials: dict) -> tuple:
    signals, score = [], 0.0
    sector = safe_get(info, "sector", "")
    mapped = SECTOR_NAME_MAP.get(sector, sector)
    pe_med = SECTOR_PE_MEDIANS.get(mapped, 20)
    ev_med = SECTOR_EV_EBITDA_MEDIANS.get(mapped, 14)
    price = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")

    # 1. Forward P/E vs sector median
    fwd_pe = safe_get(info, "forwardPE")
    if fwd_pe and fwd_pe > 0:
        if fwd_pe < pe_med:
            score += 1; signals.append(_sig(f"Fwd P/E {fwd_pe:.1f} < sector median {pe_med}", True))
        elif fwd_pe < pe_med * 1.3:
            score += 0.5; signals.append(_sig(f"Fwd P/E {fwd_pe:.1f} near sector median {pe_med}", None))
        else:
            signals.append(_sig(f"Fwd P/E {fwd_pe:.1f} above sector median {pe_med}", False))
    else:
        signals.append(_sig("Forward P/E not available", None))

    # 2. Price vs DCF
    dcf = calc_dcf(info, financials)
    if dcf and price:
        upside = (dcf["fair_value"] - float(price)) / float(price)
        if upside > 0.20:
            score += 1; signals.append(_sig(f"DCF fair ${dcf['fair_value']:.2f} → {upside*100:.0f}% upside", True))
        elif upside > 0:
            score += 0.5; signals.append(_sig(f"DCF fair ${dcf['fair_value']:.2f} → {upside*100:.0f}% upside", None))
        else:
            signals.append(_sig(f"Price above DCF fair ${dcf['fair_value']:.2f}", False))
    else:
        signals.append(_sig("DCF requires positive FCF", None))

    # 3. P/B
    pb = safe_get(info, "priceToBook")
    if pb is not None:
        if pb < 1.5:
            score += 1; signals.append(_sig(f"P/B {pb:.2f} < 1.5 (attractive)", True))
        elif pb < 3:
            score += 0.5; signals.append(_sig(f"P/B {pb:.2f} moderate", None))
        else:
            signals.append(_sig(f"P/B {pb:.2f} elevated", False))
    else:
        signals.append(_sig("P/B ratio not available", None))

    # 4. EV/EBITDA
    ev_ebitda = safe_get(info, "enterpriseToEbitda")
    if ev_ebitda and ev_ebitda > 0:
        if ev_ebitda < ev_med:
            score += 1; signals.append(_sig(f"EV/EBITDA {ev_ebitda:.1f} < sector median {ev_med}", True))
        elif ev_ebitda < ev_med * 1.3:
            score += 0.5; signals.append(_sig(f"EV/EBITDA {ev_ebitda:.1f} near sector median {ev_med}", None))
        else:
            signals.append(_sig(f"EV/EBITDA {ev_ebitda:.1f} above sector median {ev_med}", False))
    else:
        signals.append(_sig("EV/EBITDA not available", None))

    # 5. Price vs Graham Number
    graham = calc_graham_number(info)
    if graham and price:
        if graham["is_undervalued"]:
            score += 1; signals.append(_sig(f"Price below Graham Number ${graham['graham_number']:.2f}", True))
        elif float(price) < graham["graham_number"] * 1.2:
            score += 0.5; signals.append(_sig(f"Within 20% of Graham Number ${graham['graham_number']:.2f}", None))
        else:
            signals.append(_sig(f"Price above Graham Number ${graham['graham_number']:.2f}", False))
    else:
        signals.append(_sig("Graham Number requires +EPS and +Book Value", None))

    # 6. PEG
    peg = safe_get(info, "trailingPegRatio")
    if peg and peg > 0:
        if peg < 1:
            score += 1; signals.append(_sig(f"PEG {peg:.2f} < 1 (undervalued vs growth)", True))
        elif peg < 1.5:
            score += 0.5; signals.append(_sig(f"PEG {peg:.2f} reasonable", None))
        else:
            signals.append(_sig(f"PEG {peg:.2f} elevated", False))
    else:
        signals.append(_sig("PEG ratio not available", None))

    return score, signals


# ── Future score ──────────────────────────────────────────────────────────────

def score_future(info: dict, financials: dict, fmp_data: dict) -> tuple:
    signals, score = [], 0.0

    # 1. Revenue growth TTM
    rev_g = safe_get(info, "revenueGrowth")
    if rev_g is not None:
        pct = rev_g * 100
        if rev_g > 0.15:
            score += 1; signals.append(_sig(f"Revenue growth {pct:.1f}% YoY (strong)", True))
        elif rev_g > 0.05:
            score += 0.5; signals.append(_sig(f"Revenue growth {pct:.1f}% YoY", None))
        else:
            signals.append(_sig(f"Revenue growth {pct:.1f}% YoY (weak)", False))
    else:
        signals.append(_sig("Revenue growth not available", None))

    # 2. Earnings growth TTM
    earn_g = safe_get(info, "earningsGrowth")
    if earn_g is not None:
        pct = earn_g * 100
        if earn_g > 0.15:
            score += 1; signals.append(_sig(f"Earnings growth {pct:.1f}% YoY (strong)", True))
        elif earn_g > 0.05:
            score += 0.5; signals.append(_sig(f"Earnings growth {pct:.1f}% YoY", None))
        else:
            signals.append(_sig(f"Earnings growth {pct:.1f}% YoY (weak)", False))
    else:
        signals.append(_sig("Earnings growth not available", None))

    # 3. Forward P/E < TTM P/E (earnings expanding)
    fwd_pe = safe_get(info, "forwardPE")
    ttm_pe = safe_get(info, "trailingPE")
    if fwd_pe and ttm_pe and fwd_pe > 0 and ttm_pe > 0:
        if fwd_pe < ttm_pe:
            score += 1; signals.append(_sig(f"Forward P/E {fwd_pe:.1f} < TTM P/E {ttm_pe:.1f} (earnings expanding)", True))
        else:
            signals.append(_sig(f"Forward P/E {fwd_pe:.1f} ≥ TTM P/E {ttm_pe:.1f}", False))
    else:
        signals.append(_sig("P/E expansion signal not available", None))

    # 4. Analyst consensus
    rec = safe_get(info, "recommendationKey", "")
    if rec in ("strong_buy", "buy"):
        score += 1; signals.append(_sig(f"Analyst consensus: {rec.replace('_',' ').title()}", True))
    elif rec == "hold":
        score += 0.5; signals.append(_sig("Analyst consensus: Hold", None))
    elif rec in ("sell", "strong_sell"):
        signals.append(_sig(f"Analyst consensus: {rec.replace('_',' ').title()}", False))
    else:
        signals.append(_sig("Analyst recommendation not available", None))

    # 5. Price target upside
    target = safe_get(info, "targetMeanPrice")
    price = safe_get(info, "currentPrice") or safe_get(info, "regularMarketPrice")
    if target and price:
        upside = (float(target) - float(price)) / float(price)
        if upside > 0.15:
            score += 1; signals.append(_sig(f"Analyst target ${target:.2f} → {upside*100:.0f}% upside", True))
        elif upside > 0:
            score += 0.5; signals.append(_sig(f"Analyst target ${target:.2f} → {upside*100:.0f}% upside", None))
        else:
            signals.append(_sig(f"Analyst target ${target:.2f} → {upside*100:.0f}% downside", False))
    else:
        signals.append(_sig("Analyst price target not available", None))

    # 6. Forward EPS growth (FMP first, fallback yfinance)
    fwd_eps_growth = None
    ests = fmp_data.get("analyst_estimates", [])
    if len(ests) >= 2:
        try:
            fwd_eps = float(ests[0].get("estimatedEpsAvg", 0) or 0)
            cur_eps = float(ests[1].get("estimatedEpsAvg", 1) or 1)
            if cur_eps != 0:
                fwd_eps_growth = (fwd_eps - cur_eps) / abs(cur_eps)
        except Exception:
            pass
    if fwd_eps_growth is None:
        fwd = safe_get(info, "forwardEps")
        trail = safe_get(info, "trailingEps")
        if fwd and trail and float(trail) != 0:
            fwd_eps_growth = (float(fwd) - float(trail)) / abs(float(trail))
    if fwd_eps_growth is not None:
        pct = fwd_eps_growth * 100
        if fwd_eps_growth > 0.10:
            score += 1; signals.append(_sig(f"Forward EPS growth {pct:.1f}%", True))
        elif fwd_eps_growth > 0:
            score += 0.5; signals.append(_sig(f"Forward EPS growth {pct:.1f}%", None))
        else:
            signals.append(_sig(f"Forward EPS declining {pct:.1f}%", False))
    else:
        signals.append(_sig("Forward EPS growth not available", None))

    return score, signals


# ── Past score ────────────────────────────────────────────────────────────────

def score_past(info: dict, financials: dict) -> tuple:
    signals, score = [], 0.0

    # 1. ROE
    roe = safe_get(info, "returnOnEquity")
    if roe is not None:
        pct = roe * 100
        if roe > 0.15:
            score += 1; signals.append(_sig(f"ROE {pct:.1f}% (strong)", True))
        elif roe > 0.10:
            score += 0.5; signals.append(_sig(f"ROE {pct:.1f}% (moderate)", None))
        else:
            signals.append(_sig(f"ROE {pct:.1f}% (weak)", False))
    else:
        signals.append(_sig("ROE not available", None))

    # 2. ROA
    roa = safe_get(info, "returnOnAssets")
    if roa is not None:
        pct = roa * 100
        if roa > 0.05:
            score += 1; signals.append(_sig(f"ROA {pct:.1f}% (strong)", True))
        elif roa > 0.02:
            score += 0.5; signals.append(_sig(f"ROA {pct:.1f}% (moderate)", None))
        else:
            signals.append(_sig(f"ROA {pct:.1f}% (weak)", False))
    else:
        signals.append(_sig("ROA not available", None))

    # 3. Net margin
    margin = safe_get(info, "profitMargins")
    if margin is not None:
        pct = margin * 100
        if margin > 0.10:
            score += 1; signals.append(_sig(f"Net margin {pct:.1f}% (healthy)", True))
        elif margin > 0:
            score += 0.5; signals.append(_sig(f"Net margin {pct:.1f}% (positive)", None))
        else:
            signals.append(_sig(f"Net margin {pct:.1f}% (negative)", False))
    else:
        signals.append(_sig("Net margin not available", None))

    # 4. Revenue grew in 3 of last 4 years
    inc = financials.get("annual_income", pd.DataFrame())
    rev_row = bs_row(inc, "Total Revenue", "Revenue")
    if rev_row is not None and len(rev_row.dropna()) >= 4:
        revs = rev_row.dropna().values[:4]
        grew = sum(1 for i in range(len(revs)-1) if revs[i] > revs[i+1])
        if grew >= 3:
            score += 1; signals.append(_sig(f"Revenue grew in {grew}/4 recent years", True))
        elif grew >= 2:
            score += 0.5; signals.append(_sig(f"Revenue grew in {grew}/4 recent years", None))
        else:
            signals.append(_sig(f"Revenue grew in only {grew}/4 recent years", False))
    else:
        signals.append(_sig("Multi-year revenue history not available", None))

    # 5. FCF positive and growing
    cf = financials.get("annual_cf", pd.DataFrame())
    ocf_row = bs_row(cf, "Operating Cash Flow", "Cash From Operations",
                     "Total Cash From Operating Activities",
                     "Net Cash Provided By Operating Activities")
    cap_row = bs_row(cf, "Capital Expenditure", "Capital Expenditures",
                     "Purchase Of Property Plant And Equipment",
                     "Purchases Of Property Plant And Equipment")
    if ocf_row is not None and not ocf_row.dropna().empty:
        ocf_vals = ocf_row.dropna().values
        cap_vals = (cap_row.dropna().values if cap_row is not None else
                    [0] * len(ocf_vals))
        fcf_vals = [float(o) - abs(float(c)) for o, c in
                    zip(ocf_vals, list(cap_vals) + [0]*(len(ocf_vals)-len(list(cap_vals))))]
        if len(fcf_vals) >= 2 and fcf_vals[0] > 0 and fcf_vals[0] > fcf_vals[1]:
            score += 1; signals.append(_sig("FCF positive and growing YoY", True))
        elif fcf_vals and fcf_vals[0] > 0:
            score += 0.5; signals.append(_sig("FCF positive", None))
        else:
            signals.append(_sig("FCF negative", False))
    else:
        signals.append(_sig("Cash flow data not available", None))

    # 6. Altman Z
    altman = calc_altman_z(info, financials)
    if altman:
        z = altman["z_score"]
        if z > 2.99:
            score += 1; signals.append(_sig(f"Altman Z-score {z:.2f} (Safe zone)", True))
        elif z > 1.81:
            score += 0.5; signals.append(_sig(f"Altman Z-score {z:.2f} (Grey zone)", None))
        else:
            signals.append(_sig(f"Altman Z-score {z:.2f} (Distress zone)", False))
    else:
        signals.append(_sig("Altman Z-score requires balance sheet data", None))

    return score, signals


# ── Health score ──────────────────────────────────────────────────────────────

def score_health(info: dict, financials: dict) -> tuple:
    signals, score = [], 0.0

    # 1. Current ratio
    curr_ratio = safe_get(info, "currentRatio")
    if curr_ratio is not None:
        if curr_ratio > 1.5:
            score += 1; signals.append(_sig(f"Current ratio {curr_ratio:.2f} (healthy)", True))
        elif curr_ratio > 1.0:
            score += 0.5; signals.append(_sig(f"Current ratio {curr_ratio:.2f} (adequate)", None))
        else:
            signals.append(_sig(f"Current ratio {curr_ratio:.2f} (below 1 — risk)", False))
    else:
        signals.append(_sig("Current ratio not available", None))

    # 2. Debt/Equity (yfinance returns ×100)
    de = safe_get(info, "debtToEquity")
    if de is not None:
        de_actual = de / 100
        if de_actual < 1.0:
            score += 1; signals.append(_sig(f"Debt/Equity {de_actual:.2f}x (low leverage)", True))
        elif de_actual < 2.0:
            score += 0.5; signals.append(_sig(f"Debt/Equity {de_actual:.2f}x (moderate)", None))
        else:
            signals.append(_sig(f"Debt/Equity {de_actual:.2f}x (high leverage)", False))
    else:
        signals.append(_sig("Debt/Equity not available", None))

    # 3. Interest coverage
    inc = financials.get("annual_income", pd.DataFrame())
    ebit_row = bs_row(inc, "EBIT", "Operating Income", "Ebit")
    int_row  = bs_row(inc, "Interest Expense", "Net Interest Income",
                      "Interest Expense Non Operating")
    ebit     = _first_val(ebit_row)
    interest = _first_val(int_row)
    if ebit is not None and interest is not None and interest != 0:
        coverage = ebit / abs(interest)
        if coverage > 5:
            score += 1; signals.append(_sig(f"Interest coverage {coverage:.1f}x (strong)", True))
        elif coverage > 2:
            score += 0.5; signals.append(_sig(f"Interest coverage {coverage:.1f}x (adequate)", None))
        else:
            signals.append(_sig(f"Interest coverage {coverage:.1f}x (weak)", False))
    else:
        signals.append(_sig("Interest coverage data not available", None))

    # 4. Net cash position
    total_cash = float(safe_get(info, "totalCash", 0) or 0)
    total_debt = float(safe_get(info, "totalDebt", 0) or 0)
    net_cash   = total_cash - total_debt
    if total_cash > 0:
        if net_cash > 0:
            score += 1; signals.append(_sig(f"Net cash {format_large(net_cash)} (positive)", True))
        elif total_cash > total_debt * 0.5:
            score += 0.5; signals.append(_sig("Cash covers >50% of debt", None))
        else:
            signals.append(_sig(f"Net debt {format_large(total_debt - total_cash)}", False))
    else:
        signals.append(_sig("Cash/debt position not available", None))

    # 5. Operating CF positive
    cf = financials.get("annual_cf", pd.DataFrame())
    ocf_row = bs_row(cf, "Operating Cash Flow", "Cash From Operations",
                     "Total Cash From Operating Activities",
                     "Net Cash Provided By Operating Activities")
    ocf = _first_val(ocf_row)
    if ocf is None:
        ocf = safe_get(info, "operatingCashflow")
    if ocf is not None:
        if ocf > 0:
            score += 1; signals.append(_sig(f"Operating CF positive ({format_large(ocf)})", True))
        else:
            signals.append(_sig(f"Operating CF negative ({format_large(ocf)})", False))
    else:
        signals.append(_sig("Operating CF data not available", None))

    # 6. Altman Z
    altman = calc_altman_z(info, financials)
    if altman:
        z = altman["z_score"]
        if z > 2.99:
            score += 1; signals.append(_sig(f"Altman Z-score {z:.2f} (Safe)", True))
        elif z > 1.81:
            score += 0.5; signals.append(_sig(f"Altman Z-score {z:.2f} (Grey zone)", None))
        else:
            signals.append(_sig(f"Altman Z-score {z:.2f} (Distress)", False))
    else:
        signals.append(_sig("Altman Z-score not available", None))

    return score, signals


# ── Dividend score ────────────────────────────────────────────────────────────

def score_dividend(info: dict, financials: dict) -> tuple:
    signals, score = [], 0.0

    div_yield = safe_get(info, "dividendYield")
    div_rate  = safe_get(info, "dividendRate")

    # 1. Pays dividend
    pays_div = bool(div_yield and div_yield > 0)
    if pays_div:
        score += 1; signals.append(_sig("Company pays a dividend", True))
    else:
        signals.append(_sig("No dividend — score capped at 0", False))
        return 0.0, signals

    # 2. Yield > 3%
    if div_yield > 0.03:
        score += 1; signals.append(_sig(f"Dividend yield {div_yield*100:.2f}% (attractive)", True))
    elif div_yield > 0.015:
        score += 0.5; signals.append(_sig(f"Dividend yield {div_yield*100:.2f}% (moderate)", None))
    else:
        signals.append(_sig(f"Dividend yield {div_yield*100:.2f}% (low)", False))

    # 3. Payout ratio
    payout = safe_get(info, "payoutRatio")
    if payout is not None and payout > 0:
        pct = payout * 100
        if payout < 0.60:
            score += 1; signals.append(_sig(f"Payout ratio {pct:.0f}% (sustainable)", True))
        elif payout < 0.80:
            score += 0.5; signals.append(_sig(f"Payout ratio {pct:.0f}% (moderate)", None))
        else:
            signals.append(_sig(f"Payout ratio {pct:.0f}% (high — cut risk)", False))
    else:
        signals.append(_sig("Payout ratio not available", None))

    # 4. No recent dividend cut
    trail_div = safe_get(info, "trailingAnnualDividendRate")
    if trail_div is not None and div_rate and div_rate > 0:
        if float(trail_div) >= float(div_rate) * 0.9:
            score += 1; signals.append(_sig("No recent dividend cut detected", True))
        else:
            signals.append(_sig("Possible dividend reduction detected", False))
    else:
        signals.append(_sig("Dividend cut history not determinable", None))

    # 5. Dividend stability / growth proxy
    five_yr = safe_get(info, "fiveYearAvgDividendYield")
    if five_yr and five_yr > 0:
        score += 0.5; signals.append(_sig("Dividend established (5Y history present)", None))
    else:
        signals.append(_sig("5-year dividend history not available", None))

    # 6. FCF covers dividends
    cf = financials.get("annual_cf", pd.DataFrame())
    ocf_row = bs_row(cf, "Operating Cash Flow", "Cash From Operations",
                     "Total Cash From Operating Activities",
                     "Net Cash Provided By Operating Activities")
    cap_row = bs_row(cf, "Capital Expenditure", "Capital Expenditures",
                     "Purchase Of Property Plant And Equipment",
                     "Purchases Of Property Plant And Equipment")
    div_row = bs_row(cf, "Common Stock Dividends Paid", "Cash Dividends Paid",
                     "Dividends Paid", "Payment Of Dividends")

    ocf = _first_val(ocf_row)
    capex = abs(_first_val(cap_row) or 0)
    total_div_paid = _first_val(div_row)

    if ocf and total_div_paid:
        fcf = ocf - capex
        coverage = fcf / abs(float(total_div_paid))
        if coverage > 1.2:
            score += 1; signals.append(_sig(f"FCF covers dividends {coverage:.1f}x", True))
        elif coverage > 1.0:
            score += 0.5; signals.append(_sig(f"FCF barely covers dividends {coverage:.1f}x", None))
        else:
            signals.append(_sig(f"FCF insufficient to cover dividends {coverage:.1f}x", False))
    else:
        signals.append(_sig("FCF dividend coverage not determinable", None))

    return score, signals
