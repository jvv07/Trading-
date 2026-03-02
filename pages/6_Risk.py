import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from lib.portfolio import get_trades_df, compute_positions, fetch_current_prices
from lib.charts import correlation_heatmap
from lib import metrics as m

st.set_page_config(page_title="Risk", layout="wide")
st.title("Risk Dashboard")

trades_df = get_trades_df()
positions = compute_positions(trades_df)

if positions.empty:
    st.info("No open positions to analyze.")
    st.stop()

prices = fetch_current_prices(positions["symbol"].tolist())
positions["last_price"] = positions["symbol"].map(lambda s: prices.get(s))
positions["market_value"] = positions.apply(
    lambda r: r["quantity"] * r["last_price"] if r["last_price"] else r["cost_basis"], axis=1
)
total_mv = positions["market_value"].sum()
positions["weight"] = positions["market_value"] / total_mv

symbols = positions["symbol"].tolist()

@st.cache_data(ttl=3600)
def _hist_data(syms_key, period):
    syms = syms_key.split(",")
    data = yf.download(syms + ["SPY"], period=period, auto_adjust=True, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        closes = data["Close"]
    else:
        closes = data[["Close"]]; closes.columns = syms
    return closes.pct_change().dropna()

hist_returns = _hist_data(",".join(sorted(symbols)), "1y")

# Portfolio daily returns (weighted)
weights_dict = dict(zip(positions["symbol"], positions["weight"]))
port_returns = pd.Series(0.0, index=hist_returns.index)
for sym in symbols:
    if sym in hist_returns.columns:
        port_returns += hist_returns[sym] * weights_dict.get(sym, 0)

tab1, tab2, tab3, tab4 = st.tabs(["Value at Risk", "Concentration", "Correlation", "Stress Test"])

# ── VaR ───────────────────────────────────────────────────────────────────────
with tab1:
    st.subheader("Historical Value at Risk")
    st.caption("Shows the worst expected daily loss at a given confidence level based on 1-year history.")

    var95 = m.var_historical(port_returns, 0.95)
    var99 = m.var_historical(port_returns, 0.99)
    cvar95 = m.cvar_historical(port_returns, 0.95)
    cvar99 = m.cvar_historical(port_returns, 0.99)

    dollar_var95 = var95 * total_mv
    dollar_var99 = var99 * total_mv
    dollar_cvar95 = cvar95 * total_mv
    dollar_cvar99 = cvar99 * total_mv

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("VaR 95% (daily)", f"{var95*100:.2f}%", f"${dollar_var95:,.0f}")
    c2.metric("VaR 99% (daily)", f"{var99*100:.2f}%", f"${dollar_var99:,.0f}")
    c3.metric("CVaR 95% (Expected Shortfall)", f"{cvar95*100:.2f}%", f"${dollar_cvar95:,.0f}")
    c4.metric("CVaR 99%", f"{cvar99*100:.2f}%", f"${dollar_cvar99:,.0f}")

    # Return distribution with VaR lines
    r_pct = port_returns * 100
    fig = go.Figure()
    fig.add_trace(go.Histogram(x=r_pct, nbinsx=50, name="Daily Returns",
                                marker_color="#4e9af1", opacity=0.7))
    fig.add_vline(x=var95*100, line_color="#ff4b4b", line_dash="dash",
                  annotation_text="VaR 95%", annotation_position="top right")
    fig.add_vline(x=var99*100, line_color="#ff0000", line_dash="solid",
                  annotation_text="VaR 99%")
    fig.update_layout(title="Portfolio Return Distribution (1Y)",
                       xaxis_ticksuffix="%",
                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                       font_color="#fafafa",
                       xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"))
    st.plotly_chart(fig, use_container_width=True)

    # Per-position VaR
    st.subheader("VaR by Position")
    pos_var_rows = []
    for sym in symbols:
        if sym in hist_returns.columns:
            pos_var = m.var_historical(hist_returns[sym], 0.95)
            pos_mv = positions.loc[positions["symbol"] == sym, "market_value"].iloc[0]
            pos_var_rows.append({
                "Symbol": sym,
                "Weight": f"{weights_dict.get(sym,0)*100:.1f}%",
                "VaR 95% (daily)": f"{pos_var*100:.2f}%",
                "VaR 95% ($)": f"${pos_var * pos_mv:,.0f}",
            })
    if pos_var_rows:
        st.dataframe(pd.DataFrame(pos_var_rows), hide_index=True, use_container_width=True)

# ── Concentration ─────────────────────────────────────────────────────────────
with tab2:
    st.subheader("Position Concentration")
    pos_sorted = positions.sort_values("weight", ascending=False).copy()
    pos_sorted["Weight %"] = pos_sorted["weight"] * 100

    c1, c2 = st.columns(2)
    with c1:
        for _, row in pos_sorted.iterrows():
            color = "#ff4b4b" if row["Weight %"] > 30 else "#f1c14e" if row["Weight %"] > 20 else "#00d4aa"
            st.markdown(
                f"**{row['symbol']}** — `{row['Weight %']:.1f}%`  "
                f"Market Value: `${row['market_value']:,.0f}`"
            )
            st.progress(int(row["Weight %"]))

    with c2:
        fig = go.Figure(go.Pie(
            labels=pos_sorted["symbol"], values=pos_sorted["market_value"],
            hole=0.45,
            marker_colors=["#00d4aa","#4e9af1","#f1c14e","#f17c4e","#b44ef1"],
        ))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#fafafa",
                           margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    # HHI (Herfindahl-Hirschman Index)
    hhi = (pos_sorted["weight"] ** 2).sum() * 10000
    st.metric("Herfindahl-Hirschman Index (HHI)",
              f"{hhi:.0f}",
              help="< 1500: diversified | 1500–2500: moderate | > 2500: concentrated")

# ── Correlation ───────────────────────────────────────────────────────────────
with tab3:
    if len(symbols) < 2:
        st.info("Need at least 2 positions.")
    else:
        sym_returns = hist_returns[[s for s in symbols if s in hist_returns.columns]]
        st.plotly_chart(correlation_heatmap(sym_returns.corr(), "Position Correlations (1Y)"),
                        use_container_width=True)

        avg_corr = sym_returns.corr().values
        np.fill_diagonal(avg_corr, np.nan)
        mean_corr = np.nanmean(avg_corr)
        st.metric("Average Pairwise Correlation", f"{mean_corr:.2f}",
                  help="Lower is more diversified. Near 0 = uncorrelated. Near 1 = highly correlated.")

        if "SPY" in hist_returns.columns:
            st.subheader("Beta to SPY")
            spy_ret = hist_returns["SPY"]
            beta_rows = []
            for sym in symbols:
                if sym in hist_returns.columns:
                    b = m.beta(hist_returns[sym], spy_ret)
                    beta_rows.append({"Symbol": sym, "Beta": f"{b:.2f}"})
            if beta_rows:
                st.dataframe(pd.DataFrame(beta_rows), hide_index=True, use_container_width=True)

# ── Stress Test ───────────────────────────────────────────────────────────────
with tab4:
    st.subheader("Stress Test Scenarios")
    st.caption("Estimates portfolio impact assuming positions move with their beta to SPY.")

    scenarios = {
        "SPY -5% (mild selloff)": -0.05,
        "SPY -10% (correction)": -0.10,
        "SPY -20% (bear market)": -0.20,
        "SPY -30% (crash)": -0.30,
        "SPY -50% (severe crash)": -0.50,
        "SPY +5% (rally)": +0.05,
        "SPY +10% (strong rally)": +0.10,
        "SPY +20% (bull run)": +0.20,
    }

    spy_ret_s = hist_returns["SPY"] if "SPY" in hist_returns.columns else None
    scenario_rows = []
    for scenario_name, spy_move in scenarios.items():
        port_move = 0.0
        for _, row in positions.iterrows():
            sym = row["symbol"]
            if spy_ret_s is not None and sym in hist_returns.columns:
                b = m.beta(hist_returns[sym], spy_ret_s)
            else:
                b = 1.0
            sym_move = b * spy_move
            port_move += sym_move * row["weight"]

        dollar_impact = port_move * total_mv
        scenario_rows.append({
            "Scenario": scenario_name,
            "SPY Move": f"{spy_move*100:+.0f}%",
            "Est. Portfolio Move": f"{port_move*100:+.2f}%",
            "Est. Dollar Impact": f"${dollar_impact:+,.0f}",
            "Est. Portfolio Value": f"${total_mv + dollar_impact:,.0f}",
        })

    sdf = pd.DataFrame(scenario_rows)
    st.dataframe(sdf.style.applymap(
        lambda v: "color: #00d4aa" if isinstance(v, str) and v.startswith("+") else
                  "color: #ff4b4b" if isinstance(v, str) and v.startswith("-") else "",
        subset=["Est. Portfolio Move", "Est. Dollar Impact"]
    ), use_container_width=True, hide_index=True)
