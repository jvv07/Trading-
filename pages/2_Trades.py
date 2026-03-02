import streamlit as st
import pandas as pd
from datetime import datetime
from lib.supabase_client import get_client, SOLO_USER_ID

st.set_page_config(page_title="Trades", layout="wide")
st.title("Trade Log")

client = get_client()


def load_trades():
    res = client.table("trades").select("*").eq("user_id", SOLO_USER_ID).order("executed_at", desc=True).execute()
    return res.data or []


tab_log, tab_import, tab_history = st.tabs(["Log Trade", "CSV Import", "History"])

# ── Log a trade ───────────────────────────────────────────────────────────────
with tab_log:
    strat_res = client.table("strategies").select("id, name").eq("user_id", SOLO_USER_ID).eq("status", "active").execute()
    strategies = {s["name"]: s["id"] for s in (strat_res.data or [])}

    with st.form("new_trade"):
        c1, c2, c3 = st.columns(3)
        symbol = c1.text_input("Symbol").upper().strip()
        side = c2.selectbox("Side", ["buy", "sell"])
        quantity = c3.number_input("Quantity", min_value=0.0001, step=1.0, format="%.4f")

        c4, c5, c6 = st.columns(3)
        price = c4.number_input("Price ($)", min_value=0.0, step=0.01, format="%.4f")
        commission = c5.number_input("Commission ($)", min_value=0.0, step=0.01)
        executed_at = c6.date_input("Date", value=datetime.today())

        strat_names = ["— none —"] + list(strategies.keys())
        strat_choice = st.selectbox("Strategy (optional)", strat_names)
        notes_text = st.text_area("Notes (optional)", height=80)

        submitted = st.form_submit_button("Log Trade", use_container_width=True, type="primary")

    if submitted:
        if not symbol or price <= 0 or quantity <= 0:
            st.error("Symbol, price, and quantity are required.")
        else:
            payload = {
                "user_id": SOLO_USER_ID,
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
            res = client.table("trades").insert(payload).execute()
            if notes_text.strip() and res.data:
                client.table("trade_notes").insert({
                    "user_id": SOLO_USER_ID,
                    "trade_id": res.data[0]["id"],
                    "note": notes_text.strip(),
                }).execute()
            st.success(f"Logged {side.upper()} {quantity:.4g} {symbol} @ ${price:.4g}")
            st.rerun()

# ── CSV Import ────────────────────────────────────────────────────────────────
with tab_import:
    st.markdown("""
**Expected columns** (case-insensitive): `date`, `symbol`, `side`, `quantity`, `price`
Optional: `commission`
`side` values: `buy` or `sell`
""")

    template = pd.DataFrame({
        "date": ["2024-01-15", "2024-01-20"],
        "symbol": ["AAPL", "AAPL"],
        "side": ["buy", "sell"],
        "quantity": [10, 10],
        "price": [185.50, 191.00],
        "commission": [1.00, 1.00],
    })
    st.download_button("Download Template CSV", template.to_csv(index=False),
                       file_name="trade_template.csv", mime="text/csv")

    uploaded = st.file_uploader("Upload CSV", type="csv")
    if uploaded:
        try:
            df = pd.read_csv(uploaded)
            df.columns = df.columns.str.lower().str.strip()
            required = {"date", "symbol", "side", "quantity", "price"}
            missing = required - set(df.columns)
            if missing:
                st.error(f"Missing columns: {missing}")
            else:
                df["symbol"] = df["symbol"].str.upper().str.strip()
                df["side"] = df["side"].str.lower().str.strip()
                df["commission"] = df["commission"].fillna(0) if "commission" in df.columns else 0.0
                df["date"] = pd.to_datetime(df["date"]).dt.date

                st.write(f"Preview — {len(df)} trades:")
                st.dataframe(df.head(20), use_container_width=True, hide_index=True)

                if st.button("Import All", type="primary"):
                    records = []
                    for _, row in df.iterrows():
                        records.append({
                            "user_id": SOLO_USER_ID,
                            "symbol": row["symbol"],
                            "side": row["side"],
                            "quantity": float(row["quantity"]),
                            "price": float(row["price"]),
                            "commission": float(row["commission"]),
                            "executed_at": str(row["date"]),
                            "source": "manual",
                        })
                    client.table("trades").insert(records).execute()
                    st.success(f"Imported {len(records)} trades.")
                    st.rerun()
        except Exception as e:
            st.error(f"Error reading CSV: {e}")

# ── History ───────────────────────────────────────────────────────────────────
with tab_history:
    trades = load_trades()
    if not trades:
        st.info("No trades yet.")
        st.stop()

    df = pd.DataFrame(trades)
    df["executed_at"] = pd.to_datetime(df["executed_at"])
    df["notional"] = df["quantity"] * df["price"]

    # Filters
    fc1, fc2, fc3 = st.columns(3)
    sym_filter = fc1.text_input("Filter by symbol").upper().strip()
    side_filter = fc2.selectbox("Side", ["All", "buy", "sell"])
    date_range = fc3.date_input("Date range", value=(df["executed_at"].min().date(), df["executed_at"].max().date()))

    mask = pd.Series([True] * len(df))
    if sym_filter:
        mask &= df["symbol"].str.contains(sym_filter, case=False)
    if side_filter != "All":
        mask &= df["side"] == side_filter
    if len(date_range) == 2:
        mask &= (df["executed_at"].dt.date >= date_range[0]) & (df["executed_at"].dt.date <= date_range[1])

    df_filtered = df[mask].sort_values("executed_at", ascending=False)

    st.caption(f"Showing {len(df_filtered)} of {len(df)} trades")

    display = df_filtered[["executed_at", "symbol", "side", "quantity", "price", "commission", "notional"]].copy()
    display.columns = ["Date", "Symbol", "Side", "Qty", "Price", "Commission", "Notional"]
    display["Date"] = display["Date"].dt.strftime("%Y-%m-%d %H:%M")

    st.dataframe(
        display.style.format({"Price": "${:.4g}", "Commission": "${:.2f}", "Notional": "${:,.2f}"}),
        use_container_width=True, hide_index=True,
    )

    # Delete
    with st.expander("Delete a trade"):
        trade_ids = {f"{t['symbol']} {t['side']} {t['quantity']} @ ${t['price']} on {t['executed_at'][:10]}": t["id"]
                     for t in trades}
        choice = st.selectbox("Select trade to delete", list(trade_ids.keys()))
        if st.button("Delete", type="secondary"):
            client.table("trades").delete().eq("id", trade_ids[choice]).execute()
            st.success("Deleted.")
            st.rerun()
