import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from lib.auth import require_auth
from lib.supabase_client import get_client

st.set_page_config(page_title="Analytics", layout="wide")
require_auth()

st.title("Analytics")

client = get_client()
user_id = st.session_state.user.id

# ── trade data ────────────────────────────────────────────────────────────────
res = client.table("trades").select("*").eq("user_id", user_id).order("executed_at").execute()
trades = res.data or []

if not trades:
    st.info("No trades to analyze yet.")
    st.stop()

df = pd.DataFrame(trades)
df["executed_at"] = pd.to_datetime(df["executed_at"])
df["notional"] = df["quantity"] * df["price"]
df["signed_notional"] = df.apply(
    lambda r: r["notional"] if r["side"] == "sell" else -r["notional"], axis=1
)
df["realized_pnl"] = df["signed_notional"] - df["commission"]

# ── KPI row ───────────────────────────────────────────────────────────────────
total_trades = len(df)
buy_count = (df["side"] == "buy").sum()
sell_count = (df["side"] == "sell").sum()
total_commission = df["commission"].sum()
gross_pnl = df.loc[df["side"] == "sell", "notional"].sum() - df.loc[df["side"] == "buy", "notional"].sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Trades", total_trades)
c2.metric("Buys / Sells", f"{buy_count} / {sell_count}")
c3.metric("Total Commission", f"${total_commission:,.2f}")
c4.metric("Gross P&L (sells − buys)", f"${gross_pnl:,.2f}")

st.divider()

# ── cumulative P&L over time ──────────────────────────────────────────────────
df_daily = (
    df.set_index("executed_at")
    .resample("D")["realized_pnl"]
    .sum()
    .cumsum()
    .reset_index()
)
df_daily.columns = ["Date", "Cumulative P&L"]

fig = go.Figure(go.Scatter(
    x=df_daily["Date"],
    y=df_daily["Cumulative P&L"],
    mode="lines",
    line=dict(color="#00d4aa", width=2),
    fill="tozeroy",
    fillcolor="rgba(0,212,170,0.1)",
))
fig.update_layout(
    title="Cumulative P&L",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#fafafa",
    xaxis=dict(gridcolor="#2a2f3e"),
    yaxis=dict(gridcolor="#2a2f3e", tickprefix="$"),
)
st.plotly_chart(fig, use_container_width=True)

# ── volume by symbol ──────────────────────────────────────────────────────────
vol = df.groupby("symbol")["notional"].sum().reset_index().sort_values("notional", ascending=False)
fig2 = go.Figure(go.Bar(
    x=vol["symbol"],
    y=vol["notional"],
    marker_color="#4e9af1",
))
fig2.update_layout(
    title="Total Notional by Symbol",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#fafafa",
    xaxis=dict(gridcolor="#2a2f3e"),
    yaxis=dict(gridcolor="#2a2f3e", tickprefix="$"),
)
st.plotly_chart(fig2, use_container_width=True)
