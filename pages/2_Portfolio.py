import streamlit as st
import pandas as pd
import yfinance as yf
from lib.portfolio import get_trades_df, compute_positions, fetch_current_prices
from lib.charts import equity_curve, correlation_heatmap
from lib import metrics as m

from lib.style import inject_css
from lib.nav import render_nav
st.set_page_config(page_title="Portfolio", layout="wide", initial_sidebar_state="collapsed")
inject_css()
render_nav("Portfolio")
st.title("Portfolio")

trades_df = get_trades_df()
positions = compute_positions(trades_df)

if positions.empty:
    st.info("No open positions. Log trades on the Trades page.")
    st.stop()

prices = fetch_current_prices(positions["symbol"].tolist())
positions["last_price"] = positions["symbol"].map(lambda s: prices.get(s))
positions["market_value"] = positions.apply(
    lambda r: r["quantity"] * r["last_price"] if r["last_price"] else None, axis=1
)
positions["unrealized_pnl"] = positions.apply(
    lambda r: r["market_value"] - r["cost_basis"] if r["market_value"] is not None else None, axis=1
)
positions["pnl_pct"] = positions.apply(
    lambda r: r["unrealized_pnl"] / r["cost_basis"] * 100 if r["cost_basis"] else None, axis=1
)

total_mv = positions["market_value"].sum()
total_cb = positions["cost_basis"].sum()
total_upnl = positions["unrealized_pnl"].sum()
total_rpnl = positions["realized_pnl"].sum()

# ── Summary ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Market Value", f"${total_mv:,.2f}")
c2.metric("Cost Basis", f"${total_cb:,.2f}")
c3.metric("Unrealized P&L", f"${total_upnl:,.2f}",
          delta=f"{total_upnl/total_cb*100:.2f}%" if total_cb else None)
c4.metric("Realized P&L (all trades)", f"${total_rpnl:,.2f}")

st.divider()

tab1, tab2, tab3 = st.tabs(["Positions", "Allocation & Risk", "Correlation"])

# ── Tab 1: Positions table ────────────────────────────────────────────────────
with tab1:
    display = positions[["symbol","quantity","avg_cost","last_price","market_value","unrealized_pnl","pnl_pct","realized_pnl"]].copy()
    display.columns = ["Symbol","Qty","Avg Cost","Last","Mkt Value","Unreal. P&L","P&L %","Realized P&L"]
    st.dataframe(
        display.style.format({
            "Avg Cost": "${:.2f}",
            "Last": lambda v: f"${v:.2f}" if v else "N/A",
            "Mkt Value": lambda v: f"${v:,.2f}" if v else "N/A",
            "Unreal. P&L": lambda v: f"${v:,.2f}" if v else "N/A",
            "P&L %": lambda v: f"{v:.2f}%" if v else "N/A",
            "Realized P&L": "${:,.2f}",
        }).map(
            lambda v: "color: #00d4aa" if isinstance(v, str) and "%" in v and not v.startswith("-") else
                      "color: #ff4b4b" if isinstance(v, str) and v.startswith("-") else "",
            subset=["P&L %", "Unreal. P&L"],
        ),
        use_container_width=True, hide_index=True,
    )

# ── Tab 2: Allocation & Risk ──────────────────────────────────────────────────
with tab2:
    import plotly.graph_objects as go

    valid = positions.dropna(subset=["market_value"])
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Allocation by Market Value")
        fig = go.Figure(go.Pie(
            labels=valid["symbol"], values=valid["market_value"],
            hole=0.45,
            marker_colors=["#00d4aa","#4e9af1","#f1c14e","#f17c4e","#b44ef1","#4ef1c1","#f14e9a"],
        ))
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#fafafa",
                          margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Concentration Risk")
        if total_mv > 0:
            valid2 = valid.copy()
            valid2["weight"] = valid2["market_value"] / total_mv * 100
            valid2 = valid2.sort_values("weight", ascending=False)
            max_conc = valid2["weight"].iloc[0]
            top3 = valid2["weight"].iloc[:3].sum()
            st.metric("Largest Position", f"{valid2['symbol'].iloc[0]}  {max_conc:.1f}%")
            st.metric("Top 3 Concentration", f"{top3:.1f}%")
            st.metric("# Positions", len(valid2))

            for _, row in valid2.iterrows():
                st.progress(int(row["weight"]), text=f"{row['symbol']}  {row['weight']:.1f}%")

    # Beta to SPY
    st.subheader("Portfolio Beta vs SPY")
    symbols = positions["symbol"].tolist()
    if symbols:
        @st.cache_data(ttl=3600)
        def _beta_calc(syms_key):
            syms = syms_key.split(",")
            data = yf.download(syms + ["SPY"], period="1y", auto_adjust=True, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                closes = data["Close"]
            else:
                closes = data[["Close"]]
                closes.columns = syms + ["SPY"]
            rets = closes.pct_change().dropna()
            if "SPY" not in rets.columns:
                return {}
            spy_ret = rets["SPY"]
            betas = {}
            for sym in syms:
                if sym in rets.columns:
                    betas[sym] = m.beta(rets[sym], spy_ret)
            # Portfolio beta = weighted average
            return betas

        betas = _beta_calc(",".join(sorted(symbols)))
        if betas and total_mv > 0:
            weights = {row["symbol"]: row["market_value"] / total_mv
                       for _, row in positions.dropna(subset=["market_value"]).iterrows()}
            port_beta = sum(betas.get(s, 1.0) * weights.get(s, 0) for s in symbols)
            bc1, bc2 = st.columns(2)
            bc1.metric("Portfolio Beta", f"{port_beta:.2f}",
                       help="Beta > 1 = more volatile than SPY; < 1 = less volatile")
            beta_df = pd.DataFrame({"Symbol": list(betas.keys()), "Beta": list(betas.values())})
            bc2.dataframe(beta_df.style.format({"Beta": "{:.2f}"}), hide_index=True, use_container_width=True)

# ── Tab 3: Correlation ────────────────────────────────────────────────────────
with tab3:
    symbols = positions["symbol"].tolist()
    if len(symbols) < 2:
        st.info("Need at least 2 positions to compute correlation.")
    else:
        @st.cache_data(ttl=3600)
        def _corr(syms_key):
            syms = syms_key.split(",")
            data = yf.download(syms, period="1y", auto_adjust=True, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                closes = data["Close"]
            else:
                closes = data[["Close"]]
                closes.columns = syms
            return closes.pct_change().dropna().corr()

        corr = _corr(",".join(sorted(symbols)))
        st.plotly_chart(correlation_heatmap(corr, "Return Correlation (1Y)"), use_container_width=True)
        st.caption("Values near +1 = highly correlated (less diversification). Near 0 = uncorrelated. Near -1 = inversely correlated (natural hedge).")
