import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from lib.supabase_client import get_client, SOLO_USER_ID
from lib.data_fetcher import get_price

st.set_page_config(page_title="Portfolio", layout="wide")
st.title("Portfolio")

client = get_client()

res = client.table("positions").select("*").eq("user_id", SOLO_USER_ID).eq("status", "open").execute()
positions = res.data or []

if not positions:
    st.info("No open positions. Add trades to populate your portfolio.")
    st.stop()

rows = []
for p in positions:
    try:
        price = get_price(p["symbol"])
    except Exception:
        price = None
    market_val = price * p["quantity"] if price else None
    cost_basis = p["avg_cost"] * p["quantity"]
    pnl = (market_val - cost_basis) if market_val is not None else None
    rows.append({
        "Symbol": p["symbol"],
        "Qty": p["quantity"],
        "Avg Cost": p["avg_cost"],
        "Last Price": price,
        "Market Value": market_val,
        "Unrealized P&L": pnl,
        "% Change": (pnl / cost_basis * 100) if pnl is not None else None,
    })

df = pd.DataFrame(rows)

total_market = df["Market Value"].sum()
total_cost = (df["Avg Cost"] * df["Qty"]).sum()
total_pnl = df["Unrealized P&L"].sum()

c1, c2, c3 = st.columns(3)
c1.metric("Total Market Value", f"${total_market:,.2f}")
c2.metric("Total Cost Basis", f"${total_cost:,.2f}")
c3.metric("Unrealized P&L", f"${total_pnl:,.2f}", delta=f"{total_pnl/total_cost*100:.2f}%")

st.divider()

st.dataframe(
    df.style.format({
        "Avg Cost": "${:.2f}",
        "Last Price": lambda v: f"${v:.2f}" if v else "N/A",
        "Market Value": lambda v: f"${v:,.2f}" if v else "N/A",
        "Unrealized P&L": lambda v: f"${v:,.2f}" if v else "N/A",
        "% Change": lambda v: f"{v:.2f}%" if v else "N/A",
    }).applymap(
        lambda v: "color: #00d4aa" if isinstance(v, str) and v.startswith("$") and not v.startswith("$-") else
                  "color: #ff4b4b" if isinstance(v, str) and v.startswith("$-") else "",
        subset=["Unrealized P&L"]
    ),
    use_container_width=True,
    hide_index=True,
)

valid = df.dropna(subset=["Market Value"])
if not valid.empty:
    fig = go.Figure(go.Pie(
        labels=valid["Symbol"],
        values=valid["Market Value"],
        hole=0.4,
        marker_colors=["#00d4aa", "#4e9af1", "#f1c14e", "#f17c4e", "#b44ef1"],
    ))
    fig.update_layout(
        title="Allocation by Market Value",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#fafafa",
    )
    st.plotly_chart(fig, use_container_width=True)
