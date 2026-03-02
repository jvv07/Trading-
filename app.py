import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta

st.set_page_config(
    page_title="Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from lib.portfolio import get_trades_df, compute_positions, fetch_current_prices
from lib.supabase_client import get_client, SOLO_USER_ID

st.title("Dashboard")

trades_df = get_trades_df()

# ── KPI row ───────────────────────────────────────────────────────────────────
positions = compute_positions(trades_df)
total_market_value = 0.0
total_unrealized = 0.0

if not positions.empty:
    prices = fetch_current_prices(positions["symbol"].tolist())
    for _, row in positions.iterrows():
        price = prices.get(row["symbol"])
        if price:
            mv = row["quantity"] * price
            total_market_value += mv
            total_unrealized += mv - row["cost_basis"]

total_realized = trades_df["commission"].sum() * -1 if not trades_df.empty else 0.0
if not trades_df.empty:
    sells = trades_df[trades_df["side"] == "sell"]
    buys_matched = trades_df[trades_df["side"] == "buy"]
    # Simple realized: sum of sell notional - cost basis approximation
    total_realized = float(
        sells["notional"].sum() - buys_matched["notional"].sum()
    ) if not sells.empty else 0.0

open_count = len(positions)
trade_count = len(trades_df)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Portfolio Value", f"${total_market_value:,.2f}")
c2.metric("Unrealized P&L", f"${total_unrealized:,.2f}",
          delta=f"{(total_unrealized/total_market_value*100):.2f}%" if total_market_value else None)
c3.metric("Gross Realized P&L", f"${total_realized:,.2f}")
c4.metric("Open Positions", open_count)
c5.metric("Total Trades", trade_count)

st.divider()

col_left, col_right = st.columns([3, 2])

# ── recent trades ─────────────────────────────────────────────────────────────
with col_right:
    st.subheader("Recent Trades")
    if trades_df.empty:
        st.info("No trades yet.")
    else:
        recent = trades_df.sort_values("executed_at", ascending=False).head(8).copy()
        recent["Date"] = pd.to_datetime(recent["executed_at"]).dt.strftime("%m/%d %H:%M")
        recent["Notional"] = recent["notional"].map("${:,.0f}".format)
        st.dataframe(
            recent[["Date", "symbol", "side", "quantity", "price", "Notional"]].rename(
                columns={"symbol": "Symbol", "side": "Side", "quantity": "Qty", "price": "Price"}
            ),
            use_container_width=True, hide_index=True,
        )

# ── market snapshot ───────────────────────────────────────────────────────────
with col_left:
    st.subheader("Market Snapshot")
    indices = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "Russell 2000": "^RUT", "VIX": "^VIX"}

    @st.cache_data(ttl=300)
    def _market_data():
        rows = []
        for name, ticker in indices.items():
            try:
                t = yf.Ticker(ticker)
                fi = t.fast_info
                last = fi.last_price
                prev = fi.previous_close
                chg = last - prev
                pct = chg / prev * 100
                rows.append({"Index": name, "Last": last, "Change": chg, "% Change": pct})
            except Exception:
                pass
        return rows

    snap = _market_data()
    if snap:
        snap_df = pd.DataFrame(snap)
        st.dataframe(
            snap_df.style
                .format({"Last": "{:.2f}", "Change": "{:+.2f}", "% Change": "{:+.2f}%"})
                .map(lambda v: f"color: {'#00d4aa' if v >= 0 else '#ff4b4b'}" if isinstance(v, float) else "",
                          subset=["Change", "% Change"]),
            use_container_width=True, hide_index=True,
        )

    # Open positions mini table
    st.subheader("Open Positions")
    if positions.empty:
        st.info("No open positions.")
    else:
        prices = fetch_current_prices(positions["symbol"].tolist())
        pos_disp = positions.copy()
        pos_disp["Last"] = pos_disp["symbol"].map(lambda s: prices.get(s))
        pos_disp["Unreal. P&L"] = pos_disp.apply(
            lambda r: (r["Last"] - r["avg_cost"]) * r["quantity"] if r["Last"] else None, axis=1
        )
        st.dataframe(
            pos_disp[["symbol", "quantity", "avg_cost", "Last", "Unreal. P&L"]].rename(
                columns={"symbol": "Symbol", "quantity": "Qty", "avg_cost": "Avg Cost"}
            ).style.format({
                "Avg Cost": "${:.2f}",
                "Last": lambda v: f"${v:.2f}" if v else "N/A",
                "Unreal. P&L": lambda v: f"${v:,.2f}" if v else "N/A",
            }),
            use_container_width=True, hide_index=True,
        )
