import streamlit as st
import pandas as pd
from lib.supabase_client import get_client, SOLO_USER_ID
from lib.portfolio import get_trades_df
from lib import metrics as m

from lib.style import inject_css
from lib.nav import render_nav
st.set_page_config(page_title="Strategies", layout="wide", initial_sidebar_state="collapsed")
inject_css()
render_nav("Strategies")
st.title("Strategies")

client = get_client()


def load_strategies():
    res = client.table("strategies").select("*").eq("user_id", SOLO_USER_ID).order("created_at", desc=True).execute()
    return res.data or []


tab_list, tab_new = st.tabs(["Strategy List", "New Strategy"])

with tab_new:
    with st.form("new_strategy"):
        name = st.text_input("Name")
        description = st.text_area("Description")
        params_text = st.text_area(
            "Parameters (free text, e.g. RSI<30 entry, RSI>70 exit, SL 2%)",
            height=100,
        )
        submitted = st.form_submit_button("Create Strategy", use_container_width=True, type="primary")
    if submitted:
        if not name:
            st.error("Name is required.")
        else:
            client.table("strategies").insert({
                "user_id": SOLO_USER_ID,
                "name": name,
                "description": f"{description}\n\nParams: {params_text}".strip(),
            }).execute()
            st.success(f"Strategy '{name}' created.")
            st.rerun()

with tab_list:
    strategies = load_strategies()
    if not strategies:
        st.info("No strategies yet.")
        st.stop()

    trades_df = get_trades_df()

    for strat in strategies:
        sid = strat["id"]
        with st.container(border=True):
            h1, h2, h3, h4 = st.columns([4, 1, 1, 1])
            h1.markdown(f"### {strat['name']}")
            status_color = {"active": "🟢", "paused": "🟡", "archived": "⚫"}.get(strat["status"], "⚪")
            h2.markdown(f"{status_color} `{strat['status']}`")

            action = h3.selectbox("", ["—", "pause", "activate", "archive"],
                                   key=f"act_{sid}", label_visibility="collapsed")
            if action != "—":
                new_status = {"pause": "paused", "activate": "active", "archive": "archived"}[action]
                client.table("strategies").update({"status": new_status}).eq("id", sid).execute()
                st.rerun()

            if h4.button("Delete", key=f"del_{sid}", type="secondary"):
                client.table("strategies").delete().eq("id", sid).execute()
                st.rerun()

            if strat.get("description"):
                st.caption(strat["description"])

            # Performance summary for this strategy
            if not trades_df.empty and "strategy_id" in trades_df.columns:
                strat_trades = trades_df[trades_df["strategy_id"] == sid]
                if not strat_trades.empty:
                    total_trades = len(strat_trades)
                    sells = strat_trades[strat_trades["side"] == "sell"]
                    buys = strat_trades[strat_trades["side"] == "buy"]
                    gross_pnl = sells["notional"].sum() - buys["notional"].sum()
                    total_commission = strat_trades["commission"].sum()
                    net_pnl = gross_pnl - total_commission

                    mc1, mc2, mc3 = st.columns(3)
                    mc1.metric("Trades", total_trades)
                    mc2.metric("Gross P&L", f"${gross_pnl:,.2f}")
                    mc3.metric("Net P&L (after commission)", f"${net_pnl:,.2f}")
                else:
                    st.caption("_No trades linked to this strategy yet._")
