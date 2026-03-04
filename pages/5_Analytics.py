import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from lib.portfolio import get_trades_df, compute_positions, build_equity_curve
from lib.charts import (equity_curve, drawdown_chart, monthly_returns_heatmap,
                         rolling_sharpe_chart, return_distribution, bar_by_category)
from lib import metrics as m
from lib.supabase_client import get_client, SOLO_USER_ID

from lib.style import inject_css
st.set_page_config(page_title="Analytics", layout="wide")
inject_css()
st.title("Analytics")

trades_df = get_trades_df()
if trades_df.empty:
    st.info("No trades to analyze yet.")
    st.stop()

# ── Benchmark selector ────────────────────────────────────────────────────────
benchmark_options = {"S&P 500 (SPY)": "SPY", "NASDAQ (QQQ)": "QQQ", "None": None}
bm_label = st.selectbox("Benchmark", list(benchmark_options.keys()), index=0)
benchmark_ticker = benchmark_options[bm_label]

# ── Equity curve from trades ──────────────────────────────────────────────────
with st.spinner("Building equity curve..."):
    equity = build_equity_curve(trades_df.to_json())

if equity.empty:
    st.warning("Could not build equity curve — check that symbols are valid yfinance tickers.")
    st.stop()

daily_returns = equity.pct_change().dropna()

bm_series = None
if benchmark_ticker:
    @st.cache_data(ttl=3600)
    def _bm(ticker, start):
        data = yf.download(ticker, start=start, auto_adjust=True, progress=False)
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.droplevel(1)
        close = data["Close"].dropna()
        initial = float(equity.iloc[0]) if len(equity) else 1.0
        return close / close.iloc[0] * initial
    bm_series = _bm(benchmark_ticker, equity.index[0].strftime("%Y-%m-%d"))

# ── compute per-trade P&L for trade-level stats ───────────────────────────────
def trade_pnls(df):
    pnls = []
    positions = {}
    for _, t in df.sort_values("executed_at").iterrows():
        sym = t["symbol"]
        if sym not in positions:
            positions[sym] = {"qty": 0.0, "avg_cost": 0.0}
        p = positions[sym]
        if t["side"] == "buy":
            new_qty = p["qty"] + t["quantity"]
            p["avg_cost"] = (p["qty"] * p["avg_cost"] + t["quantity"] * t["price"]) / new_qty
            p["qty"] = new_qty
        elif t["side"] == "sell" and p["qty"] > 0:
            pnl = (t["price"] - p["avg_cost"]) * t["quantity"] - t["commission"]
            pnls.append(pnl)
            p["qty"] = max(0.0, p["qty"] - t["quantity"])
    return pd.Series(pnls)

trade_pnl_series = trade_pnls(trades_df)

# ── KPI row ───────────────────────────────────────────────────────────────────
stats = m.summary(daily_returns, equity, trade_pnl_series)
if benchmark_ticker and bm_series is not None:
    bm_ret = bm_series.pct_change().dropna()
    aligned = pd.concat([daily_returns, bm_ret], axis=1).dropna()
    if len(aligned.columns) == 2:
        stats["Beta"] = f"{m.beta(aligned.iloc[:,0], aligned.iloc[:,1]):.2f}"
        stats["Alpha"] = f"{m.alpha(aligned.iloc[:,0], aligned.iloc[:,1])*100:.2f}%"

n_cols = min(len(stats), 5)
cols = st.columns(n_cols)
for i, (k, v) in enumerate(stats.items()):
    cols[i % n_cols].metric(k, v)

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Equity Curve", "Drawdown", "Monthly Returns", "Trade Analysis", "By Symbol / Strategy"
])

with tab1:
    series = {"Portfolio": equity}
    if bm_series is not None:
        series[bm_label] = bm_series
    st.plotly_chart(equity_curve(series), use_container_width=True)
    st.plotly_chart(rolling_sharpe_chart(daily_returns), use_container_width=True)

with tab2:
    st.plotly_chart(drawdown_chart(equity), use_container_width=True)

    # Drawdown table: top 5 worst drawdowns
    dd = m.drawdown_series(equity)
    dd_df = dd.reset_index()
    dd_df.columns = ["Date", "Drawdown"]
    dd_df["Drawdown %"] = dd_df["Drawdown"] * 100
    worst = dd_df.nsmallest(5, "Drawdown")
    worst["Date"] = worst["Date"].dt.strftime("%Y-%m-%d")
    st.subheader("Top 5 Worst Drawdowns")
    st.dataframe(worst[["Date", "Drawdown %"]].style.format({"Drawdown %": "{:.2f}%"}),
                 hide_index=True, use_container_width=True)

with tab3:
    st.plotly_chart(monthly_returns_heatmap(daily_returns), use_container_width=True)
    st.plotly_chart(return_distribution(daily_returns), use_container_width=True)

with tab4:
    if trade_pnl_series.empty:
        st.info("No closed trades yet (need at least one sell trade).")
    else:
        tc1, tc2, tc3, tc4 = st.columns(4)
        tc1.metric("Win Rate", f"{m.win_rate(trade_pnl_series)*100:.1f}%")
        tc2.metric("Profit Factor", f"{m.profit_factor(trade_pnl_series):.2f}")
        tc3.metric("Avg Win",
                   f"${trade_pnl_series[trade_pnl_series>0].mean():.2f}" if (trade_pnl_series>0).any() else "—")
        tc4.metric("Avg Loss",
                   f"${trade_pnl_series[trade_pnl_series<0].mean():.2f}" if (trade_pnl_series<0).any() else "—")

        import plotly.graph_objects as go
        colors = ["#00d4aa" if v >= 0 else "#ff4b4b" for v in trade_pnl_series]
        fig = go.Figure(go.Bar(
            x=list(range(1, len(trade_pnl_series)+1)),
            y=trade_pnl_series.values,
            marker_color=colors,
        ))
        fig.update_layout(title="P&L per Closed Trade",
                          xaxis_title="Trade #", yaxis_tickprefix="$",
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#fafafa",
                          xaxis=dict(gridcolor="#2a2f3e"), yaxis=dict(gridcolor="#2a2f3e"))
        st.plotly_chart(fig, use_container_width=True)

with tab5:
    by_sym = trades_df.copy()
    by_sym["signed"] = by_sym.apply(
        lambda r: r["notional"] if r["side"] == "sell" else -r["notional"], axis=1
    )
    sym_pnl = by_sym.groupby("symbol")["signed"].sum().sort_values()
    st.plotly_chart(bar_by_category(sym_pnl, "P&L by Symbol"), use_container_width=True)

    if "strategy_id" in trades_df.columns and not trades_df["strategy_id"].isna().all():
        strat_res = get_client().table("strategies").select("id,name").eq("user_id", SOLO_USER_ID).execute()
        strat_map = {s["id"]: s["name"] for s in (strat_res.data or [])}
        by_strat = trades_df.copy()
        by_strat["strategy"] = by_strat["strategy_id"].map(strat_map).fillna("Untagged")
        by_strat["signed"] = by_strat.apply(
            lambda r: r["notional"] if r["side"] == "sell" else -r["notional"], axis=1
        )
        strat_pnl = by_strat.groupby("strategy")["signed"].sum().sort_values()
        st.plotly_chart(bar_by_category(strat_pnl, "P&L by Strategy"), use_container_width=True)
