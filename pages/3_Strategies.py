import streamlit as st
from lib.supabase_client import get_client, SOLO_USER_ID

st.set_page_config(page_title="Strategies", layout="wide")
st.title("Strategies")

client = get_client()

with st.expander("New Strategy", expanded=False):
    with st.form("new_strategy"):
        name = st.text_input("Name")
        description = st.text_area("Description")
        submitted = st.form_submit_button("Create", use_container_width=True)
    if submitted:
        if not name:
            st.error("Name is required.")
        else:
            client.table("strategies").insert({
                "user_id": SOLO_USER_ID,
                "name": name,
                "description": description,
            }).execute()
            st.success(f"Strategy '{name}' created.")
            st.rerun()

res = client.table("strategies").select("*").eq("user_id", SOLO_USER_ID).order("created_at", desc=True).execute()
strategies = res.data or []

if not strategies:
    st.info("No strategies yet.")
    st.stop()

for strat in strategies:
    with st.container():
        col1, col2, col3 = st.columns([4, 1, 1])
        col1.markdown(f"**{strat['name']}**  \n{strat.get('description') or ''}")
        col2.markdown(f"`{strat['status']}`")
        action = col3.selectbox(
            "Action",
            ["—", "pause", "archive"],
            key=f"action_{strat['id']}",
            label_visibility="collapsed",
        )
        if action != "—":
            new_status = "paused" if action == "pause" else "archived"
            client.table("strategies").update({"status": new_status}).eq("id", strat["id"]).execute()
            st.rerun()
        st.divider()
