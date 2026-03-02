import streamlit as st
import pandas as pd
from datetime import datetime
from lib.auth import require_auth
from lib.supabase_client import get_client

st.set_page_config(page_title="Trades", layout="wide")
require_auth()

st.title("Trade Log")

client = get_client()
user_id = st.session_state.user.id

# ── log a trade ───────────────────────────────────────────────────────────────
with st.expander("Log a Trade", expanded=False):
    with st.form("new_trade"):
        c1, c2, c3 = st.columns(3)
        symbol = c1.text_input("Symbol").upper()
        side = c2.selectbox("Side", ["buy", "sell"])
        quantity = c3.number_input("Quantity", min_value=0.0001, step=1.0)

        c4, c5, c6 = st.columns(3)
        price = c4.number_input("Price", min_value=0.0, step=0.01)
        commission = c5.number_input("Commission", min_value=0.0, step=0.01)
        executed_at = c6.date_input("Date", value=datetime.today())

        # strategy selector
        strat_res = client.table("strategies").select("id, name").eq("user_id", user_id).eq("status", "active").execute()
        strategies = {s["name"]: s["id"] for s in (strat_res.data or [])}
        strat_names = ["— none —"] + list(strategies.keys())
        strat_choice = st.selectbox("Strategy", strat_names)

        submitted = st.form_submit_button("Log Trade", use_container_width=True)

    if submitted:
        if not symbol or price <= 0 or quantity <= 0:
            st.error("Symbol, price, and quantity are required.")
        else:
            payload = {
                "user_id": user_id,
                "symbol": symbol,
                "side": side,
                "quantity": float(quantity),
                "price": float(price),
                "commission": float(commission),
                "executed_at": executed_at.isoformat(),
                "source": "manual",
            }
            if strat_choice != "— none —":
                payload["strategy_id"] = strategies[strat_choice]
            client.table("trades").insert(payload).execute()
            st.success(f"Logged {side.upper()} {quantity} {symbol} @ ${price:.2f}")
            st.rerun()

# ── trade history ─────────────────────────────────────────────────────────────
res = client.table("trades").select("*").eq("user_id", user_id).order("executed_at", desc=True).execute()
trades = res.data or []

if not trades:
    st.info("No trades logged yet.")
    st.stop()

df = pd.DataFrame(trades)
df["executed_at"] = pd.to_datetime(df["executed_at"]).dt.strftime("%Y-%m-%d %H:%M")
df["notional"] = df["quantity"] * df["price"]

display_cols = ["executed_at", "symbol", "side", "quantity", "price", "commission", "notional", "source"]
df = df[[c for c in display_cols if c in df.columns]]
df.columns = ["Date", "Symbol", "Side", "Qty", "Price", "Commission", "Notional", "Source"]

st.dataframe(
    df.style.format({"Price": "${:.2f}", "Commission": "${:.2f}", "Notional": "${:,.2f}"}),
    use_container_width=True,
    hide_index=True,
)
