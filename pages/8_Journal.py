import streamlit as st
import pandas as pd
from datetime import date
from lib.supabase_client import get_client, SOLO_USER_ID

st.set_page_config(page_title="Journal", layout="wide")
st.title("Trading Journal")

client = get_client()

MOODS = ["confident", "neutral", "uncertain", "fearful", "greedy"]
MOOD_EMOJI = {"confident": "😎", "neutral": "😐", "uncertain": "🤔", "fearful": "😰", "greedy": "🤑"}

tab_write, tab_read = st.tabs(["New Entry", "Browse Entries"])

# ── Write ─────────────────────────────────────────────────────────────────────
with tab_write:
    with st.form("journal_entry"):
        c1, c2, c3 = st.columns([2, 1, 1])
        entry_date = c1.date_input("Date", value=date.today())
        title = c2.text_input("Title (optional)")
        mood = c3.selectbox("Mood", MOODS, index=1,
                             format_func=lambda m: f"{MOOD_EMOJI[m]} {m.title()}")

        body = st.text_area("Entry", height=250,
                             placeholder="What happened in the market today? What trades did you make and why? "
                                         "What did you learn? What would you do differently?")
        tags_raw = st.text_input("Tags (comma-separated)", placeholder="momentum, earnings, mistake")

        submitted = st.form_submit_button("Save Entry", type="primary", use_container_width=True)

    if submitted:
        if not body.strip():
            st.error("Entry body is required.")
        else:
            tags = [t.strip().lower() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
            client.table("journal_entries").insert({
                "user_id": SOLO_USER_ID,
                "entry_date": str(entry_date),
                "title": title.strip() or None,
                "body": body.strip(),
                "tags": tags or None,
                "mood": mood,
            }).execute()
            st.success("Entry saved.")
            st.rerun()

# ── Browse ────────────────────────────────────────────────────────────────────
with tab_read:
    res = client.table("journal_entries").select("*").eq("user_id", SOLO_USER_ID)\
        .order("entry_date", desc=True).execute()
    entries = res.data or []

    if not entries:
        st.info("No journal entries yet.")
        st.stop()

    # Search / filter
    fc1, fc2, fc3 = st.columns(3)
    search = fc1.text_input("Search", placeholder="keyword in title or body")
    mood_filter = fc2.selectbox("Filter by mood", ["All"] + MOODS)
    tag_filter = fc3.text_input("Filter by tag")

    filtered = entries
    if search:
        filtered = [e for e in filtered if
                    search.lower() in (e.get("title") or "").lower() or
                    search.lower() in (e.get("body") or "").lower()]
    if mood_filter != "All":
        filtered = [e for e in filtered if e.get("mood") == mood_filter]
    if tag_filter:
        filtered = [e for e in filtered if tag_filter.lower() in (e.get("tags") or [])]

    st.caption(f"{len(filtered)} entries")

    for entry in filtered:
        mood_icon = MOOD_EMOJI.get(entry.get("mood", "neutral"), "📝")
        tags_str = " ".join(f"`{t}`" for t in (entry.get("tags") or []))
        title_display = entry.get("title") or entry["entry_date"]

        with st.expander(f"{mood_icon} **{entry['entry_date']}** — {title_display}  {tags_str}"):
            st.markdown(entry["body"])
            col1, col2 = st.columns([4, 1])
            col1.caption(f"Mood: {mood_icon} {entry.get('mood', '').title()}")
            if col2.button("Delete", key=f"del_{entry['id']}", type="secondary"):
                client.table("journal_entries").delete().eq("id", entry["id"]).execute()
                st.rerun()
