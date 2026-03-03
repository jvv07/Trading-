import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from scipy.stats import norm
from scipy.optimize import brentq
from datetime import datetime, date, timedelta
import warnings
warnings.filterwarnings("ignore")

from lib.style import inject_css

st.set_page_config(page_title="Options Analytics", layout="wide")
inject_css()
st.title("Options Analytics")
st.caption("Real-time options chains, implied volatility surface, Greeks, and strategy payoff simulator.")

# ── Black-Scholes core ─────────────────────────────────────────────────────────

def bs_price(S: float, K: float, T: float, r: float, sigma: float, opt: str = "call") -> float:
    if T <= 0 or sigma <= 0:
        intrinsic = max(S - K, 0) if opt == "call" else max(K - S, 0)
        return float(intrinsic)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if opt == "call":
        return float(S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))
    return float(K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1))


def bs_greeks(S: float, K: float, T: float, r: float, sigma: float, opt: str = "call") -> dict:
    if T <= 0 or sigma <= 0:
        return dict(delta=1.0 if opt == "call" else -1.0, gamma=0.0, theta=0.0, vega=0.0, rho=0.0)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    phi  = norm.pdf(d1)
    sqT  = np.sqrt(T)
    gamma  = phi / (S * sigma * sqT)
    vega   = S * phi * sqT / 100          # per 1 vol-point
    if opt == "call":
        delta = float(norm.cdf(d1))
        theta = (-(S * phi * sigma) / (2 * sqT) - r * K * np.exp(-r * T) * norm.cdf(d2)) / 365
        rho   = K * T * np.exp(-r * T) * norm.cdf(d2) / 100
    else:
        delta = float(norm.cdf(d1) - 1)
        theta = (-(S * phi * sigma) / (2 * sqT) + r * K * np.exp(-r * T) * norm.cdf(-d2)) / 365
        rho   = -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
    return dict(delta=delta, gamma=float(gamma), theta=float(theta), vega=float(vega), rho=float(rho))


def implied_vol(mkt_price: float, S: float, K: float, T: float, r: float, opt: str = "call") -> float:
    if T <= 0 or mkt_price <= 0:
        return np.nan
    intrinsic = max(S - K, 0) if opt == "call" else max(K - S, 0)
    if mkt_price < intrinsic * 0.99:
        return np.nan
    try:
        return float(brentq(
            lambda sigma: bs_price(S, K, T, r, sigma, opt) - mkt_price,
            1e-6, 20.0, maxiter=500, xtol=1e-6
        ))
    except Exception:
        return np.nan


# ── Sidebar controls ──────────────────────────────────────────────────────────
with st.sidebar:
    st.subheader("⚙ Settings")
    symbol = st.text_input("Ticker", value="AAPL").upper().strip()
    risk_free = st.slider("Risk-Free Rate (%)", 0.0, 10.0, 4.5, 0.1) / 100
    st.divider()
    st.caption("Options data via yfinance. Greeks computed with Black-Scholes.")

# ── Load ticker ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_ticker_info(sym: str):
    t = yf.Ticker(sym)
    try:
        price = t.fast_info.last_price
    except Exception:
        price = None
    return t, price

ticker, spot = load_ticker_info(symbol)
if spot is None or spot == 0:
    st.error(f"Could not fetch price for **{symbol}**. Try another ticker.")
    st.stop()

st.markdown(f"### {symbol} — Spot Price: **${spot:,.2f}**")

# Available expiries
try:
    expiries = ticker.options
except Exception:
    st.error("No options data available for this symbol.")
    st.stop()

if not expiries:
    st.error("No options data available for this symbol.")
    st.stop()

tab_chain, tab_iv, tab_oi, tab_greeks, tab_payoff = st.tabs(
    ["📋 Chain", "🌋 IV Surface", "📊 Open Interest", "🔢 Greeks Profile", "💡 Payoff Simulator"]
)

# ── Helper: load chain ────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_chain(sym: str, expiry: str):
    t = yf.Ticker(sym)
    chain = t.option_chain(expiry)
    return chain.calls, chain.puts

def days_to_expiry(exp_str: str) -> float:
    return max((datetime.strptime(exp_str, "%Y-%m-%d").date() - date.today()).days, 0) / 365.0


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Chain
# ══════════════════════════════════════════════════════════════════════════════
with tab_chain:
    sel_expiry = st.selectbox("Expiry", expiries, key="chain_expiry")
    T = days_to_expiry(sel_expiry)
    days_left = int(T * 365)
    st.caption(f"Days to expiry: **{days_left}**  |  T = {T:.4f} yrs")

    calls, puts = load_chain(symbol, sel_expiry)

    def enrich_chain(df: pd.DataFrame, opt: str) -> pd.DataFrame:
        df = df.copy()
        df["mid"] = (df["bid"] + df["ask"]) / 2
        df["mid"] = df["mid"].where(df["mid"] > 0, df["lastPrice"])
        df["IV_calc"] = df.apply(
            lambda row: implied_vol(row["mid"], spot, row["strike"], T, risk_free, opt)
            if row["mid"] > 0 else np.nan, axis=1
        )
        greeks_rows = df.apply(
            lambda row: bs_greeks(spot, row["strike"], T, risk_free,
                                   row["IV_calc"] if not np.isnan(row.get("IV_calc", np.nan)) else 0.3, opt),
            axis=1
        )
        for g in ["delta", "gamma", "theta", "vega", "rho"]:
            df[g] = greeks_rows.apply(lambda d: d[g])
        # Moneyness label
        df["moneyness"] = df["strike"].apply(
            lambda k: "ITM" if (k < spot if opt == "call" else k > spot) else
                      ("ATM" if abs(k / spot - 1) < 0.01 else "OTM")
        )
        keep = ["strike", "bid", "ask", "mid", "lastPrice", "volume", "openInterest",
                "impliedVolatility", "IV_calc", "delta", "gamma", "theta", "vega", "rho", "moneyness"]
        return df[[c for c in keep if c in df.columns]]

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### Calls")
        calls_rich = enrich_chain(calls, "call")
        atm_idx = (calls_rich["strike"] - spot).abs().idxmin()
        atm_strike = calls_rich.loc[atm_idx, "strike"]
        nearby = calls_rich[calls_rich["strike"].between(atm_strike * 0.85, atm_strike * 1.15)]
        st.dataframe(
            nearby.style.format({
                "strike": "${:.2f}", "bid": "${:.2f}", "ask": "${:.2f}", "mid": "${:.2f}",
                "lastPrice": "${:.2f}", "volume": "{:,.0f}", "openInterest": "{:,.0f}",
                "impliedVolatility": "{:.1%}", "IV_calc": "{:.1%}",
                "delta": "{:.3f}", "gamma": "{:.4f}", "theta": "{:.4f}",
                "vega": "{:.4f}", "rho": "{:.4f}",
            }).map(
                lambda v: "background-color: rgba(0,212,170,0.15)" if v == "ITM" else
                          "background-color: rgba(241,193,78,0.15)" if v == "ATM" else "",
                subset=["moneyness"]
            ).map(
                lambda v: "color: #00d4aa" if isinstance(v, float) and v > 0.5 else
                          "color: #ff4b4b" if isinstance(v, float) and v < 0.0 else "",
                subset=["delta"]
            ),
            hide_index=True, use_container_width=True
        )

    with c2:
        st.markdown("#### Puts")
        puts_rich = enrich_chain(puts, "put")
        nearby_p = puts_rich[puts_rich["strike"].between(atm_strike * 0.85, atm_strike * 1.15)]
        st.dataframe(
            nearby_p.style.format({
                "strike": "${:.2f}", "bid": "${:.2f}", "ask": "${:.2f}", "mid": "${:.2f}",
                "lastPrice": "${:.2f}", "volume": "{:,.0f}", "openInterest": "{:,.0f}",
                "impliedVolatility": "{:.1%}", "IV_calc": "{:.1%}",
                "delta": "{:.3f}", "gamma": "{:.4f}", "theta": "{:.4f}",
                "vega": "{:.4f}", "rho": "{:.4f}",
            }).map(
                lambda v: "background-color: rgba(0,212,170,0.15)" if v == "ITM" else
                          "background-color: rgba(241,193,78,0.15)" if v == "ATM" else "",
                subset=["moneyness"]
            ),
            hide_index=True, use_container_width=True
        )

    # Summary metrics
    total_call_oi = calls["openInterest"].fillna(0).sum()
    total_put_oi  = puts["openInterest"].fillna(0).sum()
    pcr = total_put_oi / total_call_oi if total_call_oi > 0 else np.nan
    call_vol = calls["volume"].fillna(0).sum()
    put_vol  = puts["volume"].fillna(0).sum()

    st.divider()
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Put/Call OI Ratio", f"{pcr:.2f}" if not np.isnan(pcr) else "N/A",
               help="< 0.7 bullish | 0.7–1.0 neutral | > 1.0 bearish")
    mc2.metric("Total Call OI", f"{total_call_oi:,.0f}")
    mc3.metric("Total Put OI", f"{total_put_oi:,.0f}")
    mc4.metric("Vol P/C Ratio", f"{put_vol/call_vol:.2f}" if call_vol > 0 else "N/A")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — IV Surface
# ══════════════════════════════════════════════════════════════════════════════
with tab_iv:
    st.subheader("Implied Volatility Surface")
    st.caption("Computed from mid-prices across all available expiries. May take a moment.")

    max_expiries = st.slider("Max expiries to load", 3, min(12, len(expiries)), min(6, len(expiries)), key="iv_exp")

    @st.cache_data(ttl=3600)
    def build_iv_surface(sym: str, expiry_list: tuple, _spot: float, rf: float):
        rows = []
        for exp in expiry_list:
            t = yf.Ticker(sym)
            try:
                ch = t.option_chain(exp)
            except Exception:
                continue
            T_exp = days_to_expiry(exp)
            if T_exp <= 0:
                continue
            dte = int(T_exp * 365)
            for opt_type, df in [("call", ch.calls), ("put", ch.puts)]:
                for _, row in df.iterrows():
                    mid = (row["bid"] + row["ask"]) / 2
                    if mid <= 0:
                        mid = row["lastPrice"]
                    if mid <= 0:
                        continue
                    strike = row["strike"]
                    moneyness = strike / _spot
                    if not (0.7 <= moneyness <= 1.3):  # focus on near-money
                        continue
                    iv = implied_vol(mid, _spot, strike, T_exp, rf, opt_type)
                    if not np.isnan(iv) and 0.01 < iv < 3.0:
                        rows.append({
                            "expiry": exp, "dte": dte, "strike": strike,
                            "moneyness": moneyness, "iv": iv * 100,
                            "type": opt_type,
                        })
        return pd.DataFrame(rows)

    with st.spinner("Computing IV surface..."):
        sel_expiries = expiries[:max_expiries]
        surf_df = build_iv_surface(symbol, tuple(sel_expiries), spot, risk_free)

    if surf_df.empty:
        st.warning("Not enough data to build IV surface.")
    else:
        iv_type = st.radio("Option type", ["call", "put", "both"], horizontal=True, key="iv_type")
        plot_df = surf_df if iv_type == "both" else surf_df[surf_df["type"] == iv_type]

        # 3D Surface
        pivot = plot_df.pivot_table(index="dte", columns="strike", values="iv", aggfunc="mean")
        pivot = pivot.sort_index()

        fig3d = go.Figure(data=[go.Surface(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale="Plasma",
            colorbar=dict(title="IV %"),
        )])
        fig3d.update_layout(
            title=f"{symbol} IV Surface",
            scene=dict(
                xaxis_title="Strike", yaxis_title="DTE", zaxis_title="IV %",
                bgcolor="rgba(0,0,0,0)",
                xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
                zaxis=dict(gridcolor="#2a2f3e"),
            ),
            paper_bgcolor="rgba(0,0,0,0)", font_color="#fafafa",
            margin=dict(l=0, r=0, t=40, b=0), height=550,
        )
        st.plotly_chart(fig3d, use_container_width=True)

        # Volatility smile for selected expiry
        st.subheader("Volatility Smile")
        smile_expiry = st.selectbox("Expiry for smile", sel_expiries, key="smile_exp")
        smile_df = surf_df[surf_df["expiry"] == smile_expiry]
        if not smile_df.empty:
            fig_smile = go.Figure()
            for opt_t, clr in [("call", "#4e9af1"), ("put", "#ff4b4b")]:
                d = smile_df[smile_df["type"] == opt_t].sort_values("strike")
                fig_smile.add_trace(go.Scatter(
                    x=d["strike"], y=d["iv"], mode="lines+markers",
                    name=opt_t.title(), line=dict(color=clr, width=2),
                    marker=dict(size=6)
                ))
            fig_smile.add_vline(x=spot, line_dash="dash", line_color="#f1c14e",
                                annotation_text=f"Spot ${spot:.2f}")
            fig_smile.update_layout(
                title=f"Volatility Smile — {smile_expiry}",
                xaxis_title="Strike", yaxis_title="Implied Volatility (%)",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#fafafa",
                xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig_smile, use_container_width=True)

        # Term structure
        st.subheader("IV Term Structure (ATM)")
        atm_ts = (
            surf_df.assign(atm_dist=(surf_df["moneyness"] - 1).abs())
            .sort_values("atm_dist")
            .groupby(["expiry", "dte"])
            .first()
            .reset_index()
            .sort_values("dte")
        )
        if not atm_ts.empty:
            fig_ts = go.Figure()
            for opt_t, clr in [("call", "#4e9af1"), ("put", "#ff4b4b")]:
                d = atm_ts[atm_ts["type"] == opt_t]
                fig_ts.add_trace(go.Scatter(
                    x=d["dte"], y=d["iv"], mode="lines+markers",
                    name=opt_t.title(), line=dict(color=clr, width=2)
                ))
            fig_ts.update_layout(
                title="ATM IV Term Structure", xaxis_title="Days to Expiry",
                yaxis_title="IV %",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#fafafa",
                xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
            )
            st.plotly_chart(fig_ts, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Open Interest & Max Pain
# ══════════════════════════════════════════════════════════════════════════════
with tab_oi:
    st.subheader("Open Interest & Max Pain")
    oi_expiry = st.selectbox("Expiry", expiries, key="oi_expiry")
    calls_oi, puts_oi = load_chain(symbol, oi_expiry)

    # OI bar chart
    all_strikes = sorted(set(calls_oi["strike"].tolist() + puts_oi["strike"].tolist()))
    c_oi = calls_oi.set_index("strike")["openInterest"].reindex(all_strikes, fill_value=0)
    p_oi = puts_oi.set_index("strike")["openInterest"].reindex(all_strikes, fill_value=0)

    fig_oi = go.Figure()
    fig_oi.add_trace(go.Bar(x=all_strikes, y=c_oi.values, name="Call OI", marker_color="#4e9af1", opacity=0.8))
    fig_oi.add_trace(go.Bar(x=all_strikes, y=-p_oi.values, name="Put OI", marker_color="#ff4b4b", opacity=0.8))
    fig_oi.add_vline(x=spot, line_dash="dash", line_color="#f1c14e",
                     annotation_text=f"Spot ${spot:.2f}", annotation_position="top")

    # Max pain calculation
    pain_rows = []
    for test_price in all_strikes:
        call_pain = sum(max(test_price - k, 0) * oi for k, oi in zip(all_strikes, c_oi.values))
        put_pain  = sum(max(k - test_price, 0) * oi for k, oi in zip(all_strikes, p_oi.values))
        pain_rows.append({"strike": test_price, "pain": (call_pain + put_pain) * 100})

    pain_df = pd.DataFrame(pain_rows)
    max_pain_strike = float(pain_df.loc[pain_df["pain"].idxmin(), "strike"])

    fig_oi.add_vline(x=max_pain_strike, line_dash="dot", line_color="#00d4aa",
                     annotation_text=f"Max Pain ${max_pain_strike:.0f}", annotation_position="top right")
    fig_oi.update_layout(
        title=f"{symbol} Open Interest — {oi_expiry}",
        barmode="overlay",
        xaxis_title="Strike", yaxis_title="Open Interest (contracts)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig_oi, use_container_width=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Max Pain Strike", f"${max_pain_strike:,.2f}")
    col2.metric("Distance to Max Pain", f"{(max_pain_strike/spot - 1)*100:+.2f}%")
    total_call_oi2 = c_oi.sum()
    total_put_oi2  = p_oi.sum()
    col3.metric("Put/Call OI Ratio", f"{total_put_oi2/total_call_oi2:.2f}" if total_call_oi2 else "N/A")

    # Pain curve
    fig_pain = go.Figure()
    fig_pain.add_trace(go.Scatter(
        x=pain_df["strike"], y=pain_df["pain"] / 1e6,
        mode="lines", name="Total Pain ($M)",
        line=dict(color="#b44ef1", width=2), fill="tozeroy",
        fillcolor="rgba(180,78,241,0.1)"
    ))
    fig_pain.add_vline(x=max_pain_strike, line_dash="dash", line_color="#00d4aa",
                       annotation_text=f"Max Pain ${max_pain_strike:.0f}")
    fig_pain.add_vline(x=spot, line_dash="dot", line_color="#f1c14e",
                       annotation_text=f"Spot ${spot:.2f}")
    fig_pain.update_layout(
        title="Max Pain Curve",
        xaxis_title="Strike", yaxis_title="Option Writer $ Profit ($M)",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
    )
    st.plotly_chart(fig_pain, use_container_width=True)

    # Volume vs OI bar comparison
    c_vol = calls_oi.set_index("strike")["volume"].reindex(all_strikes, fill_value=0)
    p_vol = puts_oi.set_index("strike")["volume"].reindex(all_strikes, fill_value=0)

    fig_vol = go.Figure()
    fig_vol.add_trace(go.Bar(x=all_strikes, y=c_vol.values, name="Call Volume", marker_color="#00d4aa", opacity=0.7))
    fig_vol.add_trace(go.Bar(x=all_strikes, y=p_vol.values, name="Put Volume", marker_color="#f1c14e", opacity=0.7))
    fig_vol.add_vline(x=spot, line_dash="dash", line_color="#fafafa")
    fig_vol.update_layout(
        title="Volume by Strike", barmode="group",
        xaxis_title="Strike", yaxis_title="Volume",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
        xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig_vol, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Greeks Profile
# ══════════════════════════════════════════════════════════════════════════════
with tab_greeks:
    st.subheader("Greeks Profile Across Strikes")

    g_expiry = st.selectbox("Expiry", expiries, key="greeks_expiry")
    T_g = days_to_expiry(g_expiry)
    calls_g, puts_g = load_chain(symbol, g_expiry)

    # Generate greeks across strike range
    all_s = sorted(set(calls_g["strike"].tolist() + puts_g["strike"].tolist()))
    # ATM ± 20%
    near_strikes = [s for s in all_s if 0.80 * spot <= s <= 1.20 * spot]
    if not near_strikes:
        near_strikes = all_s

    def get_iv_for_strike(df: pd.DataFrame, strike: float, opt: str) -> float:
        row = df[df["strike"] == strike]
        if row.empty:
            return 0.3
        mid = (row["bid"].iloc[0] + row["ask"].iloc[0]) / 2
        if mid <= 0:
            mid = row["lastPrice"].iloc[0]
        if mid <= 0:
            return float(row["impliedVolatility"].iloc[0]) if not pd.isna(row["impliedVolatility"].iloc[0]) else 0.3
        iv = implied_vol(mid, spot, strike, T_g, risk_free, opt)
        if np.isnan(iv):
            return float(row["impliedVolatility"].iloc[0]) if not pd.isna(row["impliedVolatility"].iloc[0]) else 0.3
        return iv

    greeks_list = []
    for s in near_strikes:
        iv_c = get_iv_for_strike(calls_g, s, "call")
        iv_p = get_iv_for_strike(puts_g, s, "put")
        gc = bs_greeks(spot, s, T_g, risk_free, iv_c, "call")
        gp = bs_greeks(spot, s, T_g, risk_free, iv_p, "put")
        greeks_list.append({"strike": s,
                             "call_delta": gc["delta"], "put_delta": gp["delta"],
                             "call_gamma": gc["gamma"], "put_gamma": gp["gamma"],
                             "call_theta": gc["theta"], "put_theta": gp["theta"],
                             "call_vega": gc["vega"],  "put_vega": gp["vega"]})

    gdf = pd.DataFrame(greeks_list)

    greek_figs = {
        "Delta": ("call_delta", "put_delta", "#4e9af1", "#ff4b4b"),
        "Gamma": ("call_gamma", "put_gamma", "#00d4aa", "#f1c14e"),
        "Theta": ("call_theta", "put_theta", "#b44ef1", "#f17c4e"),
        "Vega":  ("call_vega",  "put_vega",  "#4ef1c8", "#f14e9a"),
    }

    fig_g = make_subplots(rows=2, cols=2,
                           subplot_titles=list(greek_figs.keys()),
                           shared_xaxes=False)
    positions_g = [(1,1),(1,2),(2,1),(2,2)]
    for idx, (greek_name, (c_col, p_col, c_clr, p_clr)) in enumerate(greek_figs.items()):
        r, c = positions_g[idx]
        fig_g.add_trace(go.Scatter(x=gdf["strike"], y=gdf[c_col], name=f"Call {greek_name}",
                                    line=dict(color=c_clr, width=2)), row=r, col=c)
        fig_g.add_trace(go.Scatter(x=gdf["strike"], y=gdf[p_col], name=f"Put {greek_name}",
                                    line=dict(color=p_clr, width=2, dash="dash")), row=r, col=c)
        fig_g.add_vline(x=spot, line_dash="dot", line_color="#f1c14e", row=r, col=c)

    fig_g.update_layout(
        title=f"{symbol} Greeks Profile — {g_expiry}",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa", height=600,
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    for i in range(1, 5):
        fig_g.update_xaxes(gridcolor="#2a2f3e")
        fig_g.update_yaxes(gridcolor="#2a2f3e")

    st.plotly_chart(fig_g, use_container_width=True)

    # Greeks sensitivity table (ATM)
    st.subheader("ATM Option Greeks Summary")
    atm_strike_g = min(near_strikes, key=lambda x: abs(x - spot))
    iv_c_atm = get_iv_for_strike(calls_g, atm_strike_g, "call")
    iv_p_atm = get_iv_for_strike(puts_g, atm_strike_g, "put")
    call_price = bs_price(spot, atm_strike_g, T_g, risk_free, iv_c_atm, "call")
    put_price  = bs_price(spot, atm_strike_g, T_g, risk_free, iv_p_atm, "put")
    gc_atm = bs_greeks(spot, atm_strike_g, T_g, risk_free, iv_c_atm, "call")
    gp_atm = bs_greeks(spot, atm_strike_g, T_g, risk_free, iv_p_atm, "put")

    summary_df = pd.DataFrame({
        "Metric": ["Price", "IV", "Delta", "Gamma", "Theta ($/day)", "Vega (per 1%)", "Rho"],
        "Call": [f"${call_price:.3f}", f"{iv_c_atm*100:.1f}%",
                 f"{gc_atm['delta']:.4f}", f"{gc_atm['gamma']:.5f}",
                 f"${gc_atm['theta']:.4f}", f"${gc_atm['vega']:.4f}", f"${gc_atm['rho']:.4f}"],
        "Put":  [f"${put_price:.3f}", f"{iv_p_atm*100:.1f}%",
                 f"{gp_atm['delta']:.4f}", f"{gp_atm['gamma']:.5f}",
                 f"${gp_atm['theta']:.4f}", f"${gp_atm['vega']:.4f}", f"${gp_atm['rho']:.4f}"],
    })
    st.dataframe(summary_df, hide_index=True, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — Payoff Simulator
# ══════════════════════════════════════════════════════════════════════════════
with tab_payoff:
    st.subheader("Strategy Payoff Simulator")
    st.caption("Build multi-leg options strategies and visualize P&L at expiry.")

    p_expiry = st.selectbox("Expiry", expiries, key="pay_expiry")
    T_p = days_to_expiry(p_expiry)
    calls_p, puts_p = load_chain(symbol, p_expiry)

    all_strikes_p = sorted(set(calls_p["strike"].tolist() + puts_p["strike"].tolist()))

    STRATEGIES_MAP = {
        "Long Call": [("call", "long", 1, 0)],
        "Long Put": [("put", "long", 1, 0)],
        "Covered Call": [("stock", "long", 100, 0), ("call", "short", 1, 0)],
        "Protective Put": [("stock", "long", 100, 0), ("put", "long", 1, 0)],
        "Bull Call Spread": [("call", "long", 1, 0), ("call", "short", 1, 1)],
        "Bear Put Spread": [("put", "long", 1, 0), ("put", "short", 1, 1)],
        "Straddle": [("call", "long", 1, 0), ("put", "long", 1, 0)],
        "Strangle": [("call", "long", 1, 1), ("put", "long", 1, -1)],
        "Iron Condor": [("put", "short", 1, -1), ("put", "long", 1, -2),
                        ("call", "short", 1, 1), ("call", "long", 1, 2)],
        "Butterfly": [("call", "long", 1, -1), ("call", "short", 2, 0), ("call", "long", 1, 1)],
        "Custom": [],
    }

    strategy_choice = st.selectbox("Strategy Template", list(STRATEGIES_MAP.keys()))

    # Find ATM index for presets
    atm_idx_p = min(range(len(all_strikes_p)), key=lambda i: abs(all_strikes_p[i] - spot))
    atm_p = all_strikes_p[atm_idx_p]

    def get_option_price(opt_type: str, strike: float) -> float:
        if opt_type == "stock":
            return spot
        df = calls_p if opt_type == "call" else puts_p
        row = df[df["strike"] == strike]
        if row.empty:
            return bs_price(spot, strike, T_p, risk_free, 0.3, opt_type)
        mid = (row["bid"].iloc[0] + row["ask"].iloc[0]) / 2
        return mid if mid > 0 else row["lastPrice"].iloc[0]

    # Build legs
    if strategy_choice != "Custom":
        template = STRATEGIES_MAP[strategy_choice]
        legs = []
        for opt_type, direction, qty, strike_offset in template:
            target_idx = min(atm_idx_p + strike_offset, len(all_strikes_p) - 1)
            target_idx = max(target_idx, 0)
            strike = all_strikes_p[target_idx] if opt_type != "stock" else spot
            price = get_option_price(opt_type, strike)
            legs.append({
                "type": opt_type, "direction": direction,
                "quantity": qty, "strike": strike, "premium": price
            })
    else:
        n_legs = st.number_input("Number of legs", 1, 6, 2)
        legs = []
        for i in range(int(n_legs)):
            lc1, lc2, lc3, lc4, lc5 = st.columns(5)
            opt_t = lc1.selectbox(f"Type {i+1}", ["call", "put", "stock"], key=f"lt_{i}")
            dir_t = lc2.selectbox(f"Dir {i+1}", ["long", "short"], key=f"ld_{i}")
            qty_t = lc3.number_input(f"Qty {i+1}", 1, 100, 1, key=f"lq_{i}")
            if opt_t != "stock":
                st_t = lc4.selectbox(f"Strike {i+1}", all_strikes_p,
                                      index=atm_idx_p, key=f"ls_{i}")
            else:
                st_t = spot
            prem_t = get_option_price(opt_t, st_t)
            lc5.metric(f"Premium {i+1}", f"${prem_t:.3f}")
            legs.append({"type": opt_t, "direction": dir_t,
                         "quantity": qty_t, "strike": st_t, "premium": prem_t})

    # Show legs
    if legs:
        legs_df = pd.DataFrame(legs)
        st.dataframe(legs_df.style.format({
            "strike": "${:.2f}", "premium": "${:.3f}", "quantity": "{:.0f}"
        }), hide_index=True, use_container_width=True)

        # Net premium
        net_prem = sum(
            (-1 if lg["direction"] == "long" else 1) * lg["premium"] * lg["quantity"] *
            (100 if lg["type"] != "stock" else 1)
            for lg in legs
        )
        st.metric("Net Premium (+ = credit, - = debit)", f"${net_prem:,.2f}")

        # Payoff computation
        price_range = np.linspace(spot * 0.6, spot * 1.4, 500)

        def leg_payoff(price_arr, lg):
            direction_sign = 1 if lg["direction"] == "long" else -1
            opt = lg["type"]
            K = lg["strike"]
            qty = lg["quantity"]
            prem = lg["premium"]
            if opt == "stock":
                intrinsic = price_arr - K
            elif opt == "call":
                intrinsic = np.maximum(price_arr - K, 0)
            else:
                intrinsic = np.maximum(K - price_arr, 0)
            # Option multiplier 100
            mult = 100 if opt != "stock" else 1
            return direction_sign * (intrinsic * mult * qty - prem * mult * qty * (1 if lg["direction"] == "long" else -1))

        # Recalculate correctly
        total_payoff = np.zeros(len(price_range))
        for lg in legs:
            direction_sign = 1 if lg["direction"] == "long" else -1
            opt = lg["type"]
            K = lg["strike"]
            qty = lg["quantity"]
            prem = lg["premium"]
            mult = 100 if opt != "stock" else 1
            if opt == "stock":
                intrinsic = price_range - K
            elif opt == "call":
                intrinsic = np.maximum(price_range - K, 0)
            else:
                intrinsic = np.maximum(K - price_range, 0)
            total_payoff += direction_sign * (intrinsic - prem) * mult * qty

        colors = ["#00d4aa" if v >= 0 else "#ff4b4b" for v in total_payoff]
        fig_pay = go.Figure()
        fig_pay.add_trace(go.Scatter(
            x=price_range, y=total_payoff, mode="lines",
            name="P&L at Expiry", line=dict(color="#4e9af1", width=2.5)
        ))
        fig_pay.add_hline(y=0, line_color="#666", line_width=1)
        fig_pay.add_vline(x=spot, line_dash="dash", line_color="#f1c14e",
                          annotation_text=f"Spot ${spot:.2f}")
        for lg in legs:
            if lg["type"] != "stock":
                fig_pay.add_vline(x=lg["strike"], line_dash="dot", line_color="#888",
                                  annotation_text=f"K={lg['strike']:.0f}", annotation_position="bottom")

        # Breakeven lines (zero crossings)
        sign_changes = np.where(np.diff(np.sign(total_payoff)))[0]
        for idx in sign_changes:
            be = np.interp(0, [total_payoff[idx], total_payoff[idx+1]], [price_range[idx], price_range[idx+1]])
            fig_pay.add_vline(x=be, line_dash="dash", line_color="#00d4aa",
                              annotation_text=f"BE ${be:.2f}", annotation_position="top left")

        max_profit = total_payoff.max()
        max_loss = total_payoff.min()
        fig_pay.update_layout(
            title=f"{strategy_choice} — {symbol} @ ${spot:.2f} | Expiry {p_expiry}",
            xaxis_title=f"{symbol} Price at Expiry",
            yaxis_title="P&L ($)",
            yaxis_tickprefix="$",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#fafafa",
            xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )
        st.plotly_chart(fig_pay, use_container_width=True)

        mc1, mc2, mc3 = st.columns(3)
        mc1.metric("Max Profit", f"${max_profit:,.0f}" if max_profit < 1e6 else "Unlimited")
        mc2.metric("Max Loss", f"${max_loss:,.0f}" if max_loss > -1e6 else "Unlimited")
        if max_loss != 0:
            mc3.metric("Profit/Loss Ratio", f"{abs(max_profit/max_loss):.2f}x" if max_loss < 0 else "∞")
