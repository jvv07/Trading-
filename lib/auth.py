import streamlit as st
from lib.supabase_client import get_client


def require_auth():
    if "user" not in st.session_state:
        st.session_state.user = None

    if st.session_state.user:
        _render_logout()
        return

    _render_login()
    st.stop()


def _render_login():
    st.title("Trading Dashboard — Sign In")
    col, _ = st.columns([1, 2])
    with col:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign In", use_container_width=True)

        if submitted:
            try:
                client = get_client()
                res = client.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.user = res.user
                st.rerun()
            except Exception as e:
                st.error(f"Login failed: {e}")


def _render_logout():
    with st.sidebar:
        user = st.session_state.user
        st.caption(f"Signed in as **{user.email}**")
        if st.button("Sign Out", use_container_width=True):
            get_client().auth.sign_out()
            st.session_state.user = None
            st.rerun()
